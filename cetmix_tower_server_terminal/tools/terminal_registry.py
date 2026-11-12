# Copyright Cetmix OÜ 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Live terminal sessions owned by the current Odoo process.

WHY THIS FILE EXISTS
--------------------
An interactive shell is a live paramiko channel. It cannot be stored in the
database and it cannot be handed over to another process, so it has to live in
a single process for its whole lifetime while requests about it may land
anywhere.

The process that owns a session is the one serving the websocket of the browser
that opened it: the single gevent worker of a prefork deployment, or the only
process when Odoo runs threaded. That is where `ir.websocket` asks for the
session to be started, and that is where it stays.

The two directions use the two transports Odoo already provides:

- output goes through `bus.bus`, on a channel named after the session token, and
  reaches the browser through the websocket it is already connected to;
- input arrives from whichever http worker served the rpc as a postgres
  notification. `bus.bus` reaches this process exactly the same way, see
  `bus.bus._ensure_hooks` and `ImDispatch.loop` in the `bus` module.

Nothing here is shared between processes, so a session is lost if the process
that owns it is restarted. The heartbeat published by the session tells the
client when that happened.
"""

import json
import logging
import selectors
import threading
import time

import odoo
from odoo import api
from odoo.modules.registry import Registry
from odoo.tools import SQL

from odoo.addons.cetmix_tower_server.ssh.ssh import SSHConnection

from ..constants import (
    ACTION_CLOSE,
    ACTION_INPUT,
    ACTION_RESIZE,
    BROWSER_GONE_MESSAGE,
    BUS_NOTIFICATION_TYPE,
    DEFAULT_IDLE_TIMEOUT,
    DETACHED_GRACE,
    HEARTBEAT_INTERVAL,
    MAX_OUTPUT_CHUNK,
    NOTIFY_CHANNEL,
    OUTPUT_FLUSH_IDLE,
    OUTPUT_FLUSH_MAX_DELAY,
    PUMP_IDLE_SLEEP,
    SESSION_IDLE_MESSAGE,
    SHELL_CLOSED_MESSAGE,
    SSH_CONNECT_TIMEOUT,
    STATE_CLOSED,
    STATE_ERROR,
    STATE_OPEN,
)
from ..ssh.interactive_shell import InteractiveShell

_logger = logging.getLogger(__name__)

# Seconds the listener waits for a notification before checking whether it still
# has sessions to serve
LISTENER_POLL_TIMEOUT = 10

# Seconds before a listener that failed is started again
LISTENER_RETRY_DELAY = 5

# token -> TerminalSession
_SESSIONS = {}
# database name -> listener thread
_LISTENERS = {}
# Guards both dictionaries above
_LOCK = threading.RLock()


def get_session(token):
    """Return the live session for a token, if this process owns it.

    Args:
        token (str): Session token.

    Returns:
        TerminalSession: The live session, or None.
    """
    with _LOCK:
        return _SESSIONS.get(token)


def attach_websocket(token, websocket):
    """Attach a websocket to a session this process is already running.

    Args:
        token (str): Session token.
        websocket (odoo.addons.bus.websocket.Websocket): Websocket of the
            client that subscribed.

    Returns:
        bool: True if the session was found here and the websocket attached.
    """
    session = get_session(token)
    if not session:
        return False
    session.attach(websocket)
    return True


def ensure_session(record, websocket=None):
    """Start the session of a terminal record in this process, once.

    Called when a client subscribes to the bus channel of the session, which
    happens in the process that serves its websocket.

    Args:
        record (odoo.model.Model): `cx.tower.terminal.session` record to start.
        websocket (odoo.addons.bus.websocket.Websocket): Websocket the client is
            connected to, used to close the session when it goes away.

    Returns:
        TerminalSession: The session owned by this process for that record.
    """
    record.ensure_one()
    with _LOCK:
        session = _SESSIONS.get(record.session_token)
        if session:
            session.attach(websocket)
            return session
        session = TerminalSession(record, websocket)
        _SESSIONS[session.token] = session
    _ensure_listener(session.db_name)
    session.start()
    return session


def sync_websocket(websocket, tokens):
    """Detach the sessions a client is not subscribed to any more.

    The client sends the whole list of channels it wants on every subscription,
    so a session whose channel is no longer in it has been left behind: the user
    navigated away, or reloaded the page without the terminal. Leaving the
    terminal through the user interface closes the session right away; this is
    what catches the cases where the browser never got the chance to say so.

    Args:
        websocket (odoo.addons.bus.websocket.Websocket): Websocket of the client.
        tokens (list): Tokens of the terminal channels it subscribed to.
    """
    with _LOCK:
        sessions = list(_SESSIONS.values())
    for session in sessions:
        if websocket in session.websockets and session.token not in tokens:
            session.detach(websocket)


def detach_websocket(websocket):
    """Tell the sessions a websocket was watching that it is gone.

    A session left without any browser is not closed right away: it waits
    `DETACHED_GRACE` seconds for one to come back, so that a websocket which
    drops and reconnects does not cost the user their shell.

    Args:
        websocket (odoo.addons.bus.websocket.Websocket): Websocket that closed.
    """
    with _LOCK:
        sessions = list(_SESSIONS.values())
    for session in sessions:
        session.detach(websocket)


def _unregister(session):
    """Remove a session from the registry.

    Args:
        session (TerminalSession): Session to forget about.
    """
    with _LOCK:
        if _SESSIONS.get(session.token) is session:
            del _SESSIONS[session.token]


def _handle_notification(payload):
    """Route one postgres notification to the session it belongs to.

    Args:
        payload (str): Json payload of the notification.
    """
    try:
        message = json.loads(payload)
    except ValueError:
        _logger.warning("Terminal: discarding malformed notification")
        return
    session = get_session(message.get("token"))
    if not session:
        # Another process owns this session, or it is already gone.
        return
    session.handle_action(message)


def _ensure_listener(db_name):
    """Make sure this process listens for notifications of a database.

    Args:
        db_name (str): Database to listen on.
    """
    with _LOCK:
        listener = _LISTENERS.get(db_name)
        if listener is not None and listener.is_alive():
            return
        listener = threading.Thread(
            target=_listen,
            args=(db_name,),
            name=f"cx-tower-terminal-listener-{db_name}",
            daemon=True,
        )
        _LISTENERS[db_name] = listener
        listener.start()


def _listen(db_name):
    """Keep a listener on a database for as long as it has sessions.

    Args:
        db_name (str): Database to listen on.
    """
    while True:
        failed = _listen_once(db_name)
        with _LOCK:
            still_needed = any(
                session.db_name == db_name for session in _SESSIONS.values()
            )
            if not still_needed:
                # Checked and dropped under the same lock a session is
                # registered with, so a session created meanwhile always finds
                # the listener either alive or absent, never half gone.
                if _LISTENERS.get(db_name) is threading.current_thread():
                    del _LISTENERS[db_name]
                return
        if failed:
            time.sleep(LISTENER_RETRY_DELAY)


def _listen_once(db_name):
    """Dispatch notifications of a database until it has no session left.

    Args:
        db_name (str): Database to listen on.

    Returns:
        bool: True if the listener stopped because of an error, False if it
            stopped because there was nothing left to listen for.
    """
    _logger.info("Terminal: listening on %s of database %s", NOTIFY_CHANNEL, db_name)
    try:
        with (
            odoo.sql_db.db_connect(db_name).cursor() as cr,
            selectors.DefaultSelector() as selector,
        ):
            cr.execute(SQL("LISTEN %s", SQL.identifier(NOTIFY_CHANNEL)))
            # This cursor is not the one of a request: it is a connection of
            # its own, opened only to listen. The commit ends the transaction
            # the LISTEN opened, exactly as `ImDispatch.loop` does in the `bus`
            # module, so this connection does not sit in a transaction forever.
            cr.commit()  # pylint: disable=invalid-commit
            # Reading notifications needs the connection itself, the same way
            # `ImDispatch.loop` does it in the `bus` module.
            connection = cr._cnx
            selector.register(connection, selectors.EVENT_READ)
            while True:
                if selector.select(LISTENER_POLL_TIMEOUT):
                    connection.poll()
                    # Oldest first: these carry what somebody typed, and a
                    # command and the Enter that runs it can arrive in the same
                    # poll. `bus` pops from the end because it only collects
                    # channel names, where order does not matter.
                    notifications = list(connection.notifies)
                    connection.notifies.clear()
                    for notification in notifications:
                        _handle_notification(notification.payload)
                with _LOCK:
                    if not any(
                        session.db_name == db_name for session in _SESSIONS.values()
                    ):
                        return False
    except Exception:
        _logger.exception("Terminal: listener of database %s failed", db_name)
        return True


class TerminalSession:
    """Interactive shell of one terminal record, running in this process."""

    def __init__(self, record, websocket=None):
        """Read everything needed from the record, so the thread owns no cursor.

        Args:
            record (odoo.model.Model): `cx.tower.terminal.session` record.
            websocket (odoo.addons.bus.websocket.Websocket): Websocket of the
                client that asked for the session.
        """
        self.token = record.session_token
        self.record_id = record.id
        self.server_id = record.server_id.id
        self.db_name = record.env.cr.dbname
        self.uid = record.env.uid
        self.channel = record._get_bus_channel()
        self.websockets = {websocket} if websocket is not None else set()
        self.shell = None
        self._detached_since = 0.0
        self.state = STATE_OPEN
        self._closing_state = STATE_CLOSED
        self._closing_message = None
        self._connection = None
        self._stop = threading.Event()
        self._buffer = ""
        self._buffer_since = 0.0
        self._last_output_at = 0.0
        self._last_published_at = 0.0
        self._last_activity = time.monotonic()
        self._thread = None

    # -- browsers watching the session

    def attach(self, websocket):
        """Remember a browser is watching, and cancel the detach timer.

        Args:
            websocket (odoo.addons.bus.websocket.Websocket): Websocket of the
                browser, None when the session was started without one.
        """
        if websocket is not None:
            self.websockets.add(websocket)
        self._detached_since = 0.0

    def detach(self, websocket):
        """Forget a browser, and start the detach timer if it was the last one.

        Args:
            websocket (odoo.addons.bus.websocket.Websocket): Websocket that
                closed.
        """
        self.websockets.discard(websocket)
        if not self.websockets and not self._detached_since:
            self._detached_since = time.monotonic()

    # -- lifecycle

    def start(self):
        """Connect and start reading the shell in a background thread."""
        self._thread = threading.Thread(
            target=self._run,
            name=f"cx-tower-terminal-{self.token[:8]}",
            daemon=True,
        )
        self._thread.start()

    def _run(self):
        """Open the shell, then read it until the session ends."""
        try:
            self._open_shell()
        except Exception as error:
            _logger.warning(
                "Terminal: cannot open a shell on server %s: %s", self.server_id, error
            )
            self._finish(STATE_ERROR, str(error))
            return
        self._write_record(STATE_OPEN, None)
        self._publish(state=STATE_OPEN)
        try:
            self._pump()
        except Exception as error:
            _logger.exception("Terminal: session %s failed", self.record_id)
            self._finish(STATE_ERROR, str(error))

    def _open_shell(self):
        """Open an SSH shell on the server of this session.

        The connection is built from the values `cx.tower.server` already uses
        to run commands, but it is a new one: the cached client of `SSHManager`
        is shared with every command of that server, and closing a terminal must
        not close it.
        """
        with Registry(self.db_name).cursor() as cr:
            env = api.Environment(cr, self.uid, {})
            server = env["cx.tower.server"].browse(self.server_id)
            values = server._get_ssh_connection_values()
        self._connection = SSHConnection(
            host=values["host"],
            port=values["port"],
            username=values["username"],
            password=values["password"],
            ssh_key=values["ssh_key"],
            host_key=values["host_key"],
            mode=values["auth_mode"],
            timeout=SSH_CONNECT_TIMEOUT,
        )
        self.shell = InteractiveShell(self._connection)
        self.shell.open()

    def close(self, state=STATE_CLOSED, message=None):
        """Ask the session to end. Its own thread does the closing.

        Args:
            state (str): State to report to the client and store on the record.
            message (str): Reason shown in the terminal.
        """
        self._closing_state = state
        self._closing_message = message
        self._stop.set()

    def _finish(self, state, message):
        """Publish the final state, release the connection and forget the session.

        Args:
            state (str): Final state of the session.
            message (str): Reason shown in the terminal.
        """
        self.state = state
        self._flush(force=True)
        self._publish(state=state, message=message)
        self._write_record(state, message)
        if self.shell is not None:
            try:
                self.shell.close()
            finally:
                self.shell = None
        if self._connection is not None:
            try:
                self._connection.disconnect()
            except Exception:
                _logger.debug(
                    "Terminal: error while disconnecting session %s",
                    self.record_id,
                    exc_info=True,
                )
            finally:
                self._connection = None
        _unregister(self)

    # -- input

    def handle_action(self, message):
        """Run one action received through a postgres notification.

        Runs in the thread that listens for notifications, while the session
        thread is reading the shell. Both directions of a paramiko channel can
        be used at the same time, so no lock is needed between them.

        Args:
            message (dict): Decoded notification, with at least an `action` key.
        """
        action = message.get("action")
        try:
            if action == ACTION_INPUT:
                self._send_input(message.get("data") or "")
            elif action == ACTION_RESIZE:
                self._resize(message.get("cols"), message.get("rows"))
            elif action == ACTION_CLOSE:
                self.close(STATE_CLOSED, message.get("message"))
            else:
                _logger.warning("Terminal: unknown action %r", action)
        except Exception as error:
            _logger.warning("Terminal: action %s failed: %s", action, error)
            self.close(STATE_ERROR, str(error))

    def _send_input(self, data):
        """Write input to the shell.

        Args:
            data (str): Characters typed in the browser.
        """
        if not data or self.shell is None:
            return
        self._last_activity = time.monotonic()
        self.shell.send(data)

    def _resize(self, cols, rows):
        """Resize the remote pseudo terminal.

        Args:
            cols (int): New width in columns, already validated by the model.
            rows (int): New height in rows, already validated by the model.
        """
        if self.shell is None:
            return
        self._last_activity = time.monotonic()
        self.shell.resize(int(cols), int(rows))

    # -- output

    def _pump(self):
        """Read the shell and publish its output until the session ends."""
        idle_timeout = self._get_idle_timeout()
        while not self._stop.is_set():
            if not self.shell.is_active():
                self._finish(STATE_CLOSED, str(SHELL_CLOSED_MESSAGE))
                return
            output = self.shell.receive()
            if output:
                now = time.monotonic()
                self._buffer += output
                self._buffer_since = self._buffer_since or now
                self._last_output_at = now
                self._last_activity = now
                self._flush()
                continue
            self._flush()
            if time.monotonic() - self._last_activity > idle_timeout:
                self._finish(STATE_CLOSED, str(SESSION_IDLE_MESSAGE))
                return
            if (
                self._detached_since
                and time.monotonic() - self._detached_since > DETACHED_GRACE
            ):
                self._finish(STATE_CLOSED, str(BROWSER_GONE_MESSAGE))
                return
            self._heartbeat()
            self._stop.wait(PUMP_IDLE_SLEEP)
        self._finish(self._closing_state, self._closing_message)

    def _flush(self, force=False):
        """Publish buffered output once the shell went quiet or the buffer is old.

        Args:
            force (bool): Publish whatever is buffered, without waiting.
        """
        if not self._buffer:
            return
        now = time.monotonic()
        quiet_enough = now - self._last_output_at >= OUTPUT_FLUSH_IDLE
        waited_enough = now - self._buffer_since >= OUTPUT_FLUSH_MAX_DELAY
        big_enough = len(self._buffer) >= MAX_OUTPUT_CHUNK
        if not (force or quiet_enough or waited_enough or big_enough):
            return
        output, self._buffer, self._buffer_since = self._buffer, "", 0.0
        for start in range(0, len(output), MAX_OUTPUT_CHUNK):
            self._publish(output=output[start : start + MAX_OUTPUT_CHUNK])

    def _heartbeat(self):
        """Tell the client the session is still alive, every now and then."""
        if time.monotonic() - self._last_published_at < HEARTBEAT_INTERVAL:
            return
        self._publish(state=STATE_OPEN)

    def _publish(self, output="", state=None, message=None):
        """Send output and state to the browser through `bus.bus`.

        Args:
            output (str): Terminal output to write in the browser.
            state (str): Session state, defaults to the current one.
            message (str): Human readable status message.
        """
        self._last_published_at = time.monotonic()
        try:
            with Registry(self.db_name).cursor() as cr:
                env = api.Environment(cr, self.uid, {})
                env["bus.bus"]._sendone(
                    self.channel,
                    BUS_NOTIFICATION_TYPE,
                    {
                        "session_id": self.record_id,
                        "output": output,
                        "state": state or self.state,
                        "message": message and str(message) or False,
                    },
                )
        except Exception:
            _logger.exception(
                "Terminal: cannot publish the output of session %s", self.record_id
            )

    # -- record

    def _write_record(self, state, message):
        """Store the final state on the session record, if it still exists.

        Args:
            state (str): State to store.
            message (str): Message to store.
        """
        try:
            with Registry(self.db_name).cursor() as cr:
                env = api.Environment(cr, self.uid, {})
                record = env["cx.tower.terminal.session"].browse(self.record_id)
                if record.exists():
                    record.write(
                        {"state": state, "message": message and str(message) or False}
                    )
        except Exception:
            _logger.exception(
                "Terminal: cannot store the state of session %s", self.record_id
            )

    def _get_idle_timeout(self):
        """Return how long a session may stay idle before it is closed.

        Returns:
            int: Number of seconds.
        """
        try:
            with Registry(self.db_name).cursor() as cr:
                env = api.Environment(cr, self.uid, {})
                value = (
                    env["ir.config_parameter"]
                    .sudo()
                    .get_param(
                        "cetmix_tower_server_terminal.idle_timeout",
                        DEFAULT_IDLE_TIMEOUT,
                    )
                )
            return max(int(value), 60)
        except (TypeError, ValueError):
            return DEFAULT_IDLE_TIMEOUT
