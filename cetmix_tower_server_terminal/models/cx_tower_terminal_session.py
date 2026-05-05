# Copyright Cetmix OÜ 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
import uuid

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import LazyTranslate

from ..ssh.constants import (
    _MAX_PAYLOAD_LENGTH,
    _MAX_TERMINAL_COLS,
    _MAX_TERMINAL_ROWS,
    _MIN_TERMINAL_COLS,
    _MIN_TERMINAL_ROWS,
    _SEND_READ_IDLE_SECONDS,
    _STATE_SELECTION,
)

_logger = logging.getLogger(__name__)
_lt = LazyTranslate(__name__, default_lang="en_US")

_BROKER_START_LOCK = threading.Lock()


class CxTowerTerminalSession(models.TransientModel):
    _name = "cx.tower.terminal.session"
    _description = "Cetmix Tower Terminal Session"
    _transient_max_hours = 12

    _MAX_PAYLOAD_LENGTH = _MAX_PAYLOAD_LENGTH
    _MIN_TERMINAL_COLS = _MIN_TERMINAL_COLS
    _MAX_TERMINAL_COLS = _MAX_TERMINAL_COLS
    _MIN_TERMINAL_ROWS = _MIN_TERMINAL_ROWS
    _MAX_TERMINAL_ROWS = _MAX_TERMINAL_ROWS
    _SEND_READ_IDLE_SECONDS = _SEND_READ_IDLE_SECONDS

    # ── per-process pusher thread registry ───────────────────────────────────
    # Each entry lives only in the worker that started it.  The broker's
    # _active_subscribers set is the shared source of truth: only one pusher
    # can hold the subscribe stream at a time across all workers.
    _PUSHER_THREADS: dict = {}
    _PUSHER_STOP_EVENTS: dict = {}
    _PUSHER_LOCK = threading.RLock()

    name = fields.Char(required=True, readonly=True)
    session_token = fields.Char(
        required=True,
        readonly=True,
        default=lambda self: uuid.uuid4().hex,
    )
    server_id = fields.Many2one(
        comodel_name="cx.tower.server",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    jet_id = fields.Many2one(
        comodel_name="cx.tower.jet",
        readonly=True,
        ondelete="cascade",
    )
    state = fields.Selection(
        selection=lambda self: self._selection_state(),
        default=lambda self: self._default_state(),
        required=True,
        readonly=True,
    )
    message = fields.Char(readonly=True)

    # ── broker IPC ────────────────────────────────────────────────────────────

    @api.model
    def _selection_state(self):
        """Return the list of valid state values for the state field.

        Returns:
            list: List of (value, label) selection tuples.
        """
        return _STATE_SELECTION

    @api.model
    def _default_state(self):
        """Return the default value for the state field.

        Returns:
            str: The default state value ('open').
        """
        return "open"

    @staticmethod
    def _broker_socket_path():
        """Return the UNIX socket path used to communicate with the broker.

        Returns:
            str: Absolute path to the broker Unix-domain socket file.
        """
        return f"/tmp/tower_terminal_broker_{os.getuid()}.sock"

    @staticmethod
    def _broker_script_path():
        """Return the absolute path to the terminal broker Python script.

        Returns:
            str: Normalised absolute path to terminal_broker.py.
        """
        return os.path.normpath(
            os.path.join(os.path.dirname(__file__), "..", "ssh", "terminal_broker.py")
        )

    @classmethod
    def _ensure_broker(cls):
        """Make sure the terminal broker daemon is running.

        Starts the broker process if it is not already listening on its
        socket and waits up to 5 seconds for it to become ready.

        Raises:
            RuntimeError: If the broker process cannot be started or does
                not become ready within the allowed timeout.
        """
        sock_path = cls._broker_socket_path()
        if cls._broker_ping(sock_path):
            return
        with _BROKER_START_LOCK:
            if cls._broker_ping(sock_path):
                return
            try:
                subprocess.Popen(
                    [sys.executable, cls._broker_script_path()],
                    close_fds=True,
                    start_new_session=True,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as exc:
                raise RuntimeError(f"Failed to start terminal broker: {exc}") from exc
            for _ in range(20):
                time.sleep(0.25)
                if cls._broker_ping(sock_path):
                    return
            raise RuntimeError("Terminal broker did not start within timeout.")

    @staticmethod
    def _broker_ping(sock_path):
        """Return True if the broker socket accepts a connection.

        Args:
            sock_path (str): Path to the Unix-domain socket to probe.

        Returns:
            bool: True if the broker responded, False on any socket error.
        """
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(1.0)
                s.connect(sock_path)
            return True
        except OSError:
            return False

    def _broker_call(self, request, sock_timeout=30.0):
        """Send one request to the broker and return the response dict.

        Retries once after restarting the broker if the first attempt
        fails with an OSError.

        Args:
            request (dict): JSON-serialisable request payload to send.
            sock_timeout (float): Socket timeout in seconds. Defaults to 30.0.

        Returns:
            dict: Parsed JSON response from the broker.

        Raises:
            RuntimeError: If both connection attempts fail.
        """
        sock_path = self._broker_socket_path()
        last_exc = None
        for attempt in range(2):
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                    s.settimeout(sock_timeout)
                    s.connect(sock_path)
                    s.sendall((json.dumps(request) + "\n").encode())
                    return json.loads(s.makefile().readline())
            except OSError as exc:
                last_exc = exc
                if attempt == 0:
                    self._ensure_broker()
        raise RuntimeError("Terminal broker is unavailable.") from last_exc

    # ── input validation ──────────────────────────────────────────────────────

    def _sanitize_terminal_size(self, cols, rows):
        """Normalize terminal dimensions received from the web client.

        Args:
            cols (int): Column count to sanitize.
            rows (int): Row count to sanitize.

        Returns:
            tuple: Clamped (cols, rows) within allowed bounds.

        Raises:
            ValidationError: If cols or rows cannot be converted to int.
        """
        try:
            sanitized_cols = int(cols)
            sanitized_rows = int(rows)
        except (TypeError, ValueError) as err:
            raise ValidationError(self.env._("Invalid terminal size.")) from err

        return (
            min(max(sanitized_cols, self._MIN_TERMINAL_COLS), self._MAX_TERMINAL_COLS),
            min(max(sanitized_rows, self._MIN_TERMINAL_ROWS), self._MAX_TERMINAL_ROWS),
        )

    def _sanitize_read_timeout(self, options=None):
        """Normalize and clamp a caller-provided read timeout value.

        Args:
            options (dict): Options dict that may contain a 'read_timeout'
                key. Ignored if not a dict.

        Returns:
            float: Clamped timeout between 0.0 and 2.0 seconds.
        """
        if not isinstance(options, dict):
            return 0.0

        try:
            timeout_seconds = float(options.get("read_timeout", 0.0))
        except (TypeError, ValueError):
            return 0.0

        return min(max(timeout_seconds, 0.0), 2.0)

    # ── pusher thread management ──────────────────────────────────────────────

    @classmethod
    def _run_output_pusher(cls, db_name, uid, session_id, session_token, stop_event):
        """Daemon thread: subscribes to broker output stream and pushes to bus.bus.

        One pusher runs globally per session token across all workers. The
        broker enforces this via its _active_subscribers set: if another worker
        already holds the stream, the subscribe call returns an error and this
        thread exits immediately. When the worker process dies the subscriber
        socket closes, the broker releases the slot, and the next watchdog
        call (terminal_read) starts a fresh pusher in whatever worker handles it.

        Args:
            db_name (str): Odoo database name used to obtain a registry cursor.
            uid (int): UID of the user owning the terminal session.
            session_id (int): Database ID of the terminal session record.
            session_token (str): Unique token identifying the broker session.
            stop_event (threading.Event): Set this event to request thread exit.
        """
        import odoo
        from odoo.modules.registry import Registry

        sock_path = cls._broker_socket_path()
        bus_channel = f"terminal_{session_token}"

        while not stop_event.is_set():
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                    sock.settimeout(5.0)
                    sock.connect(sock_path)
                    sock.settimeout(None)  # switch to blocking for streaming
                    sock.sendall(
                        (
                            json.dumps({"action": "subscribe", "token": session_token})
                            + "\n"
                        ).encode()
                    )
                    f = sock.makefile("r")
                    for line in f:
                        if stop_event.is_set():
                            return
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            msg = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        _default_state = _STATE_SELECTION[0][0]
                        output = msg.get("output", "")
                        state = msg.get("state", _default_state)
                        # Broker rejected the subscribe (another pusher already active)
                        if msg.get("status") == "error":
                            _logger.debug(
                                "Output pusher: broker rejected subscribe for %s (%s)",
                                session_token[:8],
                                msg.get("message"),
                            )
                            return
                        if not output and state == _default_state:
                            continue
                        try:
                            registry = Registry(db_name)
                            with registry.cursor() as cr:
                                env = odoo.api.Environment(cr, uid, {})
                                env["bus.bus"]._sendone(
                                    bus_channel,
                                    "terminal.output",
                                    {
                                        "session_id": session_id,
                                        "output": output,
                                        "state": state,
                                        "message": msg.get("message"),
                                    },
                                )
                        except Exception:
                            _logger.exception(
                                "Output pusher: bus publish failed for session %s",
                                session_id,
                            )
                        if state != _default_state:
                            return
            except OSError as exc:
                if stop_event.is_set():
                    return
                _logger.warning(
                    "Output pusher: broker socket error for session %s: %s",
                    session_id,
                    exc,
                )
                time.sleep(1.0)

    def _start_output_pusher(self):
        """Start a pusher thread for this session if none is running.

        A pusher thread subscribes to the broker output stream and forwards
        terminal output to bus.bus. Only one pusher can be active per token
        in the current worker process.
        """
        self.ensure_one()
        token = self.session_token
        with type(self)._PUSHER_LOCK:
            existing = type(self)._PUSHER_THREADS.get(token)
            if existing and existing.is_alive():
                return
            stop_event = threading.Event()
            t = threading.Thread(
                target=type(self)._run_output_pusher,
                args=(
                    self.env.cr.dbname,
                    self.env.uid,
                    self.id,
                    token,
                    stop_event,
                ),
                name=f"tower-pusher-{token[:8]}",
                daemon=True,
            )
            type(self)._PUSHER_THREADS[token] = t
            type(self)._PUSHER_STOP_EVENTS[token] = stop_event
            t.start()

    def _stop_output_pusher(self):
        """Signal the pusher thread for this session to stop."""
        self.ensure_one()
        token = self.session_token
        with type(self)._PUSHER_LOCK:
            stop_event = type(self)._PUSHER_STOP_EVENTS.pop(token, None)
            type(self)._PUSHER_THREADS.pop(token, None)
        if stop_event:
            stop_event.set()

    # ── session lifecycle ─────────────────────────────────────────────────────

    @api.model
    def action_open_for_server(self, server_id, jet_id=False):
        """Create a terminal session for a server and return its client action.

        Args:
            server_id (int): ID of the cx.tower.server record.
            jet_id (int): Optional ID of the cx.tower.jet record.

        Returns:
            dict: Odoo client action dict to open the terminal UI.

        Raises:
            ValidationError: If the server or jet is not found, or if the
                jet does not belong to the given server.
        """
        server = self.env["cx.tower.server"].browse(server_id).exists()
        if not server:
            raise ValidationError(self.env._("Server not found."))
        server.check_access("read")

        jet = self.env["cx.tower.jet"]
        if jet_id:
            jet = self.env["cx.tower.jet"].browse(jet_id).exists()
            if not jet:
                raise ValidationError(self.env._("Jet not found."))
            jet.check_access("read")
            if jet.server_id != server:
                raise ValidationError(
                    self.env._("The selected jet does not belong to this server.")
                )

        name = self.env._("Terminal: %(server)s", server=server.name)
        if jet:
            name = self.env._(
                "Terminal: %(server)s / %(jet)s",
                server=server.name,
                jet=jet.name,
            )

        session = self.create(
            {
                "name": name,
                "server_id": server.id,
                "jet_id": jet.id if jet else False,
            }
        )
        session._open_broker_session()
        return session._get_client_action()

    def _build_broker_open_request(self):
        """Assemble the broker 'open' payload from this session's server config.

        Returns:
            dict: Request payload ready to pass to _broker_call.

        Raises:
            ValidationError: If the host key is missing and is required.
        """
        self.ensure_one()
        server = self.server_id.sudo()
        host_key = server._get_secret_value("host_key")
        skip_host_key = server.skip_host_key
        if (
            not host_key
            and not skip_host_key
            and (server.ip_v4_address or server.ip_v6_address)
        ):
            raise ValidationError(
                self.env._(
                    "Host key not found for server %(server)s", server=server.name
                )
            )
        return {
            "action": "open",
            "token": self.session_token,
            "host": server.ip_v4_address or server.ip_v6_address,
            "port": server.ssh_port,
            "username": server.ssh_username,
            "password": server._get_ssh_password(),
            "ssh_key": server._get_ssh_key(),
            "host_key": host_key if host_key and not skip_host_key else None,
            "mode": server.ssh_auth_mode,
        }

    def _open_broker_session(self):
        """Ask the broker to open an SSH session for this DB record.

        On success, writes state='open' and starts the output pusher thread.
        On failure, writes state='error' and re-raises a ValidationError.

        Raises:
            ValidationError: If the broker rejects the open request or any
                exception occurs during session establishment.
        """
        self.ensure_one()
        try:
            request = self._build_broker_open_request()
            resp = self._broker_call(request)
            if resp.get("status") != "ok":
                raise ValidationError(
                    resp.get("message") or self.env._("Unknown broker error.")
                )
            self.write({"state": self._default_state(), "message": False})
        except ValidationError:
            _logger.exception("Failed to open broker session %s", self.id)
            self.write({"state": "error", "message": str(sys.exc_info()[1])})
            raise
        except Exception as err:
            _logger.exception("Failed to open broker session %s", self.id)
            self.write({"state": "error", "message": str(err)})
            raise ValidationError(
                self.env._("Failed to open terminal session: %(err)s", err=err)
            ) from err
        # Start the output pusher that feeds bus.bus from the broker stream
        self._start_output_pusher()

    def _get_client_action(self):
        """Build the client action that opens the terminal UI.

        Returns:
            dict: Odoo ir.actions.client dict referencing the terminal tag.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "cetmix_tower_server_terminal.terminal",
            "name": self.name,
            "params": {
                "session_id": self.id,
                "session_token": self.session_token,
                "title": self.name,
            },
        }

    def _apply_broker_response(self, resp):
        """Sync broker state to the DB record and build the RPC response dict.

        Args:
            resp (dict): Raw response dict returned by the broker.

        Returns:
            dict: Normalised response with 'output', 'state', and 'message'
                keys.
        """
        self.ensure_one()
        default_state = self._default_state()
        state = resp.get("state", "closed")
        message = resp.get("message") or False
        output = resp.get("output", "")
        # Persist terminal-closed/error state back to the DB record
        if state != default_state and self.state == default_state:
            self.write({"state": state, "message": message})
        return {"output": output, "state": state, "message": message}

    # ── public RPC methods ────────────────────────────────────────────────────

    def terminal_read(self):
        """Return initial output and ensure the output pusher is running.

        Called once on mount by the frontend to get the shell banner and
        start the bus push stream. Also used as a watchdog every ~15 s to
        restart the pusher if the worker that owned it was recycled.

        Returns:
            dict: Response dict with 'output', 'state', and 'message' keys.
        """
        self.ensure_one()
        self.check_access("read")
        resp = self._broker_call({"action": "read", "token": self.session_token})
        # Restart pusher if it died (e.g. previous worker was recycled)
        if resp.get("state") == self._default_state():
            self._start_output_pusher()
        return self._apply_broker_response(resp)

    def terminal_send(self, payload, options=None):
        """Send input to the terminal. Output is delivered via bus.bus.

        Args:
            payload (str): Text or control characters to send to the shell.
            options (dict): Optional extra parameters (currently unused).

        Returns:
            dict: Response dict with 'output', 'state', and 'message' keys.

        Raises:
            ValidationError: If payload is not a string or exceeds the
                maximum allowed length.
        """
        self.ensure_one()
        self.check_access("read")
        if not isinstance(payload, str):
            raise ValidationError(self.env._("Invalid terminal payload."))
        if len(payload) > self._MAX_PAYLOAD_LENGTH:
            raise ValidationError(self.env._("Terminal payload is too large."))

        resp = self._broker_call(
            {
                "action": "send",
                "token": self.session_token,
                "payload": payload,
            }
        )
        return self._apply_broker_response(resp)

    def terminal_close(self):
        """Close the active terminal session and return its final state.

        Returns:
            dict: Response dict with state='closed' and a disconnect message.
        """
        self.ensure_one()
        self.check_access("read")
        self._stop_output_pusher()
        try:
            self._broker_call({"action": "close", "token": self.session_token})
        except Exception:
            _logger.exception(
                "terminal_close: broker call failed for session %s", self.id
            )
        self.write({"state": "closed", "message": self.env._("Terminal disconnected.")})
        return {
            "output": "",
            "state": "closed",
            "message": self.env._("Terminal disconnected."),
        }

    def terminal_reconnect(self):
        """Reconnect the terminal session and return the initial output.

        Closes the existing broker session, reopens it, and returns the
        initial shell banner.

        Returns:
            dict: Response dict with 'output', 'state', and 'message' keys.
        """
        self.ensure_one()
        self.check_access("read")
        self._stop_output_pusher()
        try:
            self._broker_call({"action": "close", "token": self.session_token})
        except Exception:
            _logger.exception(
                "terminal_reconnect: broker close failed for session %s", self.id
            )
        self._open_broker_session()
        resp = self._broker_call({"action": "read", "token": self.session_token})
        return self._apply_broker_response(resp)

    def terminal_resize(self, cols, rows):
        """Resize the remote PTY to match the current browser viewport.

        Args:
            cols (int): New column count for the terminal.
            rows (int): New row count for the terminal.

        Returns:
            dict: Response dict with 'output', 'state', and 'message' keys.
        """
        self.ensure_one()
        self.check_access("read")
        sanitized_cols, sanitized_rows = self._sanitize_terminal_size(cols, rows)
        resp = self._broker_call(
            {
                "action": "resize",
                "token": self.session_token,
                "cols": sanitized_cols,
                "rows": sanitized_rows,
            }
        )
        return self._apply_broker_response(resp)

    def terminal_debug_ping(self):
        """Compatibility no-op for stale frontend assets still calling this RPC.

        Returns:
            dict: Response dict with 'output', 'state', and 'message' keys.
        """
        self.ensure_one()
        self.check_access("read")
        resp = self._broker_call({"action": "ping", "token": self.session_token})
        return self._apply_broker_response(resp)

    def unlink(self):
        """Close broker sessions and stop pushers before deleting records.

        Returns:
            bool: True if all records were deleted successfully.
        """
        for session in self:
            session._stop_output_pusher()
            try:
                self._broker_call({"action": "close", "token": session.session_token})
            except Exception:
                _logger.exception(
                    "unlink: broker close failed for session %s", session.id
                )
        return super().unlink()
