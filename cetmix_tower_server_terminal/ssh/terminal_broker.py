#!/usr/bin/env python3
# Copyright Cetmix OÜ 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Cetmix Tower – terminal session broker.

WHY THIS PROCESS EXISTS
-----------------------
An interactive SSH session is a live TCP connection backed by an in-memory
paramiko Channel object.  It cannot be serialized to the database or shared
between OS processes via shared memory — it *must* live in exactly one
persistent process for its entire lifetime.

In Odoo's multi-worker (prefork) setup each HTTP request can land on a
different worker process, so storing sessions in a worker's RAM causes
"Terminal session is no longer available." errors the instant a second
worker handles a request.

The canonical solution inside the Odoo/OCA ecosystem for this class of
problem is a dedicated coordinator process that is reachable from every
worker.  OCA's ``queue_job`` module follows the same pattern: its
``QueueJobRunner`` is a long-lived process that owns shared state (the job
queue), launched via a monkey-patch of ``PreforkServer`` (see
``queue_job/jobrunner/__init__.py``).  Our broker uses a simpler approach:
it is started as a subprocess on first use and communicates with workers
via a Unix-domain socket.

A plain library (rpyc, multiprocessing.managers …) would solve the same
problem with a different wire protocol but would still require this same
architectural pattern — a persistent process owning the SSH connections.

Runs as a lightweight daemon shared by all Odoo worker processes.
Workers talk to it over a Unix-domain socket using newline-delimited JSON
(one request → one response per connection).

The broker is started automatically by CxTowerTerminalSession._ensure_broker()
when the first terminal is opened.  Do NOT run this file manually.

Protocol
--------
Request  (worker → broker): JSON object + newline
Response (broker → worker): JSON object + newline

Actions
-------
open    {action, token, host, port, username, password?, ssh_key?,
         host_key?, mode}
read    {action, token}
send    {action, token, payload, read_timeout?}
resize  {action, token, cols, rows}
close   {action, token}
ping    {action, token}

Every response contains at least {status, state, message, output}.
status is "ok" or "error".
"""

import fcntl
import importlib.util as _ilu
import json
import logging
import os
import socket
import sys
import threading
import time
import types as _types

# Load SSH classes directly from source files to avoid triggering Odoo module
# __init__.py files (which require the 'odoo' package) when the broker is
# launched as a standalone subprocess.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(os.path.dirname(_THIS_DIR))  # .../cetmix-tower/

# 1. Load SSHConnection from cetmix_tower_server/ssh/ssh.py by direct path.
_ssh_path = os.path.join(_REPO_ROOT, "cetmix_tower_server", "ssh", "ssh.py")
_ssh_spec = _ilu.spec_from_file_location("_cx_tower_ssh", _ssh_path)
_ssh_mod = _ilu.module_from_spec(_ssh_spec)
_ssh_spec.loader.exec_module(_ssh_mod)  # type: ignore[union-attr]
SSHConnection = _ssh_mod.SSHConnection  # noqa: E402

# 2. Pre-populate sys.modules so that cetmix_tower_server_terminal/ssh/ssh.py can
#    resolve 'from cetmix_tower_server.ssh.ssh import SSHConnection' without
#    loading the Odoo-dependent parent __init__.py files.
for _pkg in ("cetmix_tower_server", "cetmix_tower_server.ssh"):
    sys.modules.setdefault(_pkg, _types.ModuleType(_pkg))
sys.modules["cetmix_tower_server.ssh.ssh"] = _ssh_mod

# 3. Load InteractiveShell from local ssh.py by direct path.
_shell_path = os.path.join(_THIS_DIR, "ssh.py")
_shell_spec = _ilu.spec_from_file_location("_cx_tower_shell", _shell_path)
_shell_mod = _ilu.module_from_spec(_shell_spec)
_shell_spec.loader.exec_module(_shell_mod)  # type: ignore[union-attr]
InteractiveShell = _shell_mod.InteractiveShell  # noqa: E402

# 4. Load shared constants (no side effects, safe to import directly).
_constants_path = os.path.join(_THIS_DIR, "constants.py")
_constants_spec = _ilu.spec_from_file_location("_cx_tower_constants", _constants_path)
_constants_mod = _ilu.module_from_spec(_constants_spec)
_constants_spec.loader.exec_module(_constants_mod)  # type: ignore[union-attr]
_STATE_SELECTION = _constants_mod._STATE_SELECTION
_BROKER_IDLE_TIMEOUT = _constants_mod._BROKER_IDLE_TIMEOUT
_BROKER_CLEANUP_INTERVAL = _constants_mod._BROKER_CLEANUP_INTERVAL
_BROKER_INITIAL_READ_TIMEOUT = _constants_mod._BROKER_INITIAL_READ_TIMEOUT
_BROKER_INITIAL_READ_IDLE = _constants_mod._BROKER_INITIAL_READ_IDLE
_BROKER_ACTIVE_READ_SLEEP = _constants_mod._BROKER_ACTIVE_READ_SLEEP
_BROKER_IDLE_READ_SLEEP = _constants_mod._BROKER_IDLE_READ_SLEEP
_BROKER_ACTIVITY_WINDOW = _constants_mod._BROKER_ACTIVITY_WINDOW
_BROKER_MAX_BUFFER_BYTES = _constants_mod._BROKER_MAX_BUFFER_BYTES

# ---------------------------------------------------------------------------
# Logging – write to a temp file so broker errors are diagnosable without
# needing to capture the subprocess's stderr.  Restrict to owner-only so
# SSH traces and hostnames are not world-readable.
# ---------------------------------------------------------------------------
_LOG_PATH = f"/tmp/tower_terminal_broker_{os.getuid()}.log"
logging.basicConfig(
    level=logging.WARNING,
    filename=_LOG_PATH,
    format="%(asctime)s [broker-%(process)d] %(levelname)s %(message)s",
)
os.chmod(_LOG_PATH, 0o600)
_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Session store
# ---------------------------------------------------------------------------
_sessions: dict = {}
_sessions_lock = threading.RLock()

# Tokens whose subscriber (streaming push) connection is currently active.
# Only one subscriber per session is allowed at a time; enforced atomically
# under _sessions_lock.  When the subscriber socket closes (worker dies etc.)
# the finally block in _action_subscribe_stream removes the token.
_active_subscribers: set = set()


# ---------------------------------------------------------------------------
# _BrokerSession
# ---------------------------------------------------------------------------
class _BrokerSession:
    """SSH interactive terminal session managed by the broker process."""

    def __init__(self, token: str, connection: SSHConnection):
        """Open a paramiko shell and start the background reader thread."""
        self.token = token
        self.connection = connection
        self.shell = InteractiveShell(connection)
        self.shell.open()
        self.buffer = ""
        self.output_condition = threading.Condition()
        self.stop_event = threading.Event()
        self.state = _STATE_SELECTION[0][0]  # "open"
        self.message = None
        self.last_output_at = 0.0
        self.last_activity = time.time()
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name=f"broker-reader-{token[:8]}",
            daemon=True,
        )
        self._reader_thread.start()

    # -- activity tracking --------------------------------------------------

    def touch(self):
        """Update the last-activity timestamp to prevent idle cleanup."""
        self.last_activity = time.time()

    # -- output buffer ------------------------------------------------------

    def _append_output(self, output: str):
        """Append output to the buffer, capping it at _BROKER_MAX_BUFFER_BYTES."""
        if not output:
            return
        with self.output_condition:
            self.buffer += output
            # Enforce ring-buffer cap: discard the oldest bytes when the buffer
            # exceeds _BROKER_MAX_BUFFER_BYTES so a stalled client cannot cause
            # unbounded memory growth in the broker process.
            if len(self.buffer) > _BROKER_MAX_BUFFER_BYTES:
                self.buffer = self.buffer[-_BROKER_MAX_BUFFER_BYTES :]
            self.last_output_at = time.monotonic()
            self.output_condition.notify_all()

    def consume_output(self) -> str:
        """Atomically drain and return the current output buffer."""
        with self.output_condition:
            out = self.buffer
            self.buffer = ""
            return out

    def wait_for_output(
        self, timeout_seconds: float = 0.0, idle_seconds: float = 0.03
    ) -> str:
        """Block up to timeout_seconds and return accumulated output once idle."""
        if timeout_seconds <= 0:
            return self.consume_output()
        deadline = time.monotonic() + timeout_seconds
        with self.output_condition:
            while True:
                if self.buffer:
                    remaining = deadline - time.monotonic()
                    idle_for = time.monotonic() - self.last_output_at
                    if remaining <= 0 or idle_for >= idle_seconds:
                        out = self.buffer
                        self.buffer = ""
                        return out
                    self.output_condition.wait(min(idle_seconds - idle_for, remaining))
                    continue
                remaining = deadline - time.monotonic()
                if remaining <= 0 or self.stop_event.is_set():
                    return ""
                self.output_condition.wait(remaining)

    # -- state management ---------------------------------------------------

    def set_state(self, state: str, message: str | None = None):
        """Update session state and wake any waiters on the output condition."""
        self.state = state
        self.message = message
        with self.output_condition:
            self.output_condition.notify_all()

    # -- reader thread ------------------------------------------------------

    def _reader_loop(self):
        """Background thread: read shell output and feed the output buffer."""
        try:
            while not self.stop_event.is_set():
                if not self.shell.is_active():
                    self.set_state("closed", "The remote shell was closed.")
                    return
                output = self.shell.receive()
                if output:
                    self.touch()
                    self._append_output(output)
                    continue
                sleep = _BROKER_IDLE_READ_SLEEP
                if time.time() - self.last_activity <= _BROKER_ACTIVITY_WINDOW:
                    sleep = _BROKER_ACTIVE_READ_SLEEP
                time.sleep(sleep)
        except Exception as err:
            _logger.exception("Reader loop error for session %s", self.token)
            self.set_state("error", f"Terminal read error: {err}")

    # -- resize -------------------------------------------------------------

    def resize(self, cols: int, rows: int):
        """Resize the remote PTY to the given dimensions."""
        self.shell.resize(cols, rows)
        self.touch()

    # -- close --------------------------------------------------------------

    def close(self):
        """Shut down the reader thread, the shell, and the SSH connection."""
        self.stop_event.set()
        with self.output_condition:
            self.output_condition.notify_all()
        try:
            self.shell.close()
        finally:
            try:
                self.connection.disconnect()
            except Exception:
                _logger.debug(
                    "Error disconnecting SSH connection for session %s",
                    self.token,
                    exc_info=True,
                )
        if self._reader_thread.is_alive():
            self._reader_thread.join(timeout=1.0)


# ---------------------------------------------------------------------------
# Action helpers
# ---------------------------------------------------------------------------


def _ok(state: str = "open", message: str | None = None, output: str = "") -> dict:
    """Build a successful broker response dict."""
    return {"status": "ok", "state": state, "message": message, "output": output}


def _err(message: str) -> dict:
    """Build an error broker response dict."""
    return {
        "status": "error",
        "state": "error",
        "message": message,
        "output": "",
    }


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------


def _action_open(data: dict) -> dict:
    """Open a new SSH session for the given token and return the shell banner."""
    token = data["token"]

    # Close any existing session with this token first
    with _sessions_lock:
        old = _sessions.pop(token, None)
    if old:
        try:
            old.close()
        except Exception:
            _logger.debug(
                "Error closing previous broker session %s during reopen",
                token,
                exc_info=True,
            )

    try:
        connection = SSHConnection(
            host=data["host"],
            port=int(data["port"]),
            username=data["username"],
            password=data.get("password"),
            ssh_key=data.get("ssh_key"),
            host_key=data.get("host_key"),
            mode=data.get("mode", "p"),
            timeout=60,
        )
        session = _BrokerSession(token, connection)
    except Exception as exc:
        _logger.exception("Failed to open broker session %s", token)
        return _err(str(exc))

    initial = session.wait_for_output(
        timeout_seconds=_BROKER_INITIAL_READ_TIMEOUT,
        idle_seconds=_BROKER_INITIAL_READ_IDLE,
    )

    with _sessions_lock:
        _sessions[token] = session

    return _ok(output=initial)


def _action_read(data: dict) -> dict:
    """Return buffered output for an existing session without blocking."""
    token = data["token"]
    with _sessions_lock:
        session = _sessions.get(token)

    if not session:
        return _ok(
            state="closed",
            message="Terminal session is no longer available.",
        )

    # Check if the underlying shell died
    if not session.shell.is_active() and session.state == "open":
        session.set_state("closed", "The remote shell was closed.")

    if session.state != "open":
        with _sessions_lock:
            _sessions.pop(token, None)
        output = session.consume_output()
        try:
            session.close()
        except Exception:
            _logger.debug(
                "Error closing broker session %s after terminal end",
                token,
                exc_info=True,
            )
        return _ok(state=session.state, message=session.message, output=output)

    session.touch()
    return _ok(output=session.consume_output())


def _action_send(data: dict) -> dict:
    """Send payload to the remote shell.  Output flows via the subscriber stream."""
    token = data["token"]
    payload = data.get("payload", "")

    with _sessions_lock:
        session = _sessions.get(token)

    if not session:
        return _ok(
            state="closed",
            message="Terminal session is no longer available.",
        )

    if not session.shell.is_active():
        return _ok(state="closed", message="The remote shell was closed.")

    try:
        session.shell.send(payload)
        session.touch()
        return _ok()
    except Exception as exc:
        _logger.exception("Send error for session %s", token)
        session.set_state("error", str(exc))
        return _ok(state="error", message=str(exc))


def _action_subscribe_stream(data: dict, conn: socket.socket):
    """Stream output to the caller until the session ends or the socket closes.

    Only one subscriber per session token is allowed at a time.  If another
    subscriber is already active the connection receives an error and closes.
    When the caller's socket closes (e.g. worker process recycled) the token
    is automatically released so the next worker can claim it.
    """
    token = data["token"]

    with _sessions_lock:
        if token in _active_subscribers:
            try:
                conn.sendall((json.dumps(_err("Already subscribed")) + "\n").encode())
            except OSError:
                _logger.debug(
                    "Failed to notify duplicate subscriber for session %s",
                    token,
                    exc_info=True,
                )
            return
        _active_subscribers.add(token)

    try:
        conn.settimeout(None)  # blocking reads — no hard deadline
        while True:
            with _sessions_lock:
                session = _sessions.get(token)

            if not session:
                try:
                    conn.sendall(
                        (
                            json.dumps(_ok(state="closed", message="Session ended."))
                            + "\n"
                        ).encode()
                    )
                except OSError:
                    _logger.debug(
                        "Failed to notify closed session %s to subscriber",
                        token,
                        exc_info=True,
                    )
                return

            # Block until output arrives or 1-second timeout
            output = session.wait_for_output(timeout_seconds=1.0, idle_seconds=0.02)
            state = session.state
            message = session.message

            # Nothing to push and session is still open — loop again
            if not output and state == "open":
                continue

            try:
                conn.sendall(
                    (
                        json.dumps(
                            {"output": output or "", "state": state, "message": message}
                        )
                        + "\n"
                    ).encode()
                )
            except OSError:
                return  # Caller disconnected (worker died etc.)

            if state != "open":
                return  # Session ended — subscriber done
    finally:
        with _sessions_lock:
            _active_subscribers.discard(token)


def _action_resize(data: dict) -> dict:
    """Resize the remote PTY for the given session."""
    token = data["token"]
    try:
        cols = int(data.get("cols", 80))
        rows = int(data.get("rows", 24))
    except (TypeError, ValueError) as exc:
        return _err(f"Invalid resize dimensions: {exc}")

    with _sessions_lock:
        session = _sessions.get(token)

    if not session:
        return _ok(state="closed", message="Terminal session is no longer available.")

    try:
        session.resize(cols, rows)
        return _ok()
    except Exception as exc:
        return _err(str(exc))


def _action_close(data: dict) -> dict:
    """Close the SSH session for the given token and remove it from the store."""
    token = data["token"]
    with _sessions_lock:
        session = _sessions.pop(token, None)
    if session:
        try:
            session.close()
        except Exception:
            _logger.exception("Error closing broker session %s", token)
    return _ok(state="closed")


def _action_ping(data: dict) -> dict:
    """Touch the session and return its current state (keepalive / health-check)."""
    token = data["token"]
    with _sessions_lock:
        session = _sessions.get(token)
    if session:
        session.touch()
        return _ok(state=session.state, message=session.message)
    return _ok(state="closed", message="Terminal session is no longer available.")


_HANDLERS = {
    "open": _action_open,
    "read": _action_read,
    "send": _action_send,
    "resize": _action_resize,
    "close": _action_close,
    "ping": _action_ping,
    # "subscribe" is handled directly in _handle_client (streaming, not req/resp)
}


def _dispatch(data: dict) -> dict:
    """Route a decoded request dict to the appropriate action handler."""
    action = data.get("action")
    handler = _HANDLERS.get(action)
    if not handler:
        return _err(f"Unknown action: {action!r}")
    return handler(data)


# ---------------------------------------------------------------------------
# Client connection handler
# ---------------------------------------------------------------------------


def _handle_client(conn: socket.socket):
    """Serve one Odoo worker connection: read requests, write responses."""
    try:
        with conn:
            conn.settimeout(30.0)
            f = conn.makefile("r")
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError as exc:
                    try:
                        conn.sendall(
                            (
                                json.dumps(_err(f"JSON decode error: {exc}")) + "\n"
                            ).encode()
                        )
                    except Exception:
                        _logger.debug(
                            "Failed to send JSON decode error response",
                            exc_info=True,
                        )
                    continue

                if data.get("action") == "subscribe":
                    # Hand the connection off to the streaming handler.
                    # It keeps the socket open until the session ends or caller dies.
                    _action_subscribe_stream(data, conn)
                    return

                try:
                    response = _dispatch(data)
                except Exception as exc:
                    _logger.exception("Dispatch error")
                    response = _err(str(exc))
                try:
                    conn.sendall((json.dumps(response) + "\n").encode())
                except Exception:
                    break
    except Exception:
        _logger.exception("Unhandled error in client handler")


# ---------------------------------------------------------------------------
# Cleanup loop
# ---------------------------------------------------------------------------


def _cleanup_loop():
    """Periodically close idle or dead sessions."""
    while True:
        time.sleep(_BROKER_CLEANUP_INTERVAL)
        now = time.time()
        to_close = []
        with _sessions_lock:
            for token, session in list(_sessions.items()):
                if (
                    now - session.last_activity > _BROKER_IDLE_TIMEOUT
                    or session.state != "open"
                    or not session.shell.is_active()
                ):
                    to_close.append((token, session))
            for token, _ in to_close:
                _sessions.pop(token, None)

        for token, session in to_close:
            try:
                session.close()
            except Exception:
                _logger.exception("Cleanup error for session %s", token)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def _socket_path() -> str:
    """Return the UNIX socket path for this broker instance."""
    return f"/tmp/tower_terminal_broker_{os.getuid()}.sock"


def _lock_path() -> str:
    """Return the lock file path used to prevent duplicate broker processes."""
    return f"/tmp/tower_terminal_broker_{os.getuid()}.lock"


def main():
    """Start the broker daemon: bind the Unix socket and accept worker connections."""
    sock_path = _socket_path()
    lock_path = _lock_path()

    # Acquire an exclusive file lock so only one broker instance runs.
    # When the process exits (normally or via signal), the OS releases the lock.
    lock_fd = open(lock_path, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        # Another broker is already running – exit silently.
        lock_fd.close()
        sys.exit(0)

    lock_fd.write(str(os.getpid()) + "\n")
    lock_fd.flush()

    # Remove stale socket file if present
    try:
        os.unlink(sock_path)
    except FileNotFoundError:
        _logger.debug("No stale broker socket to remove at startup: %s", sock_path)

    # Set umask to 0o177 before bind so the socket is created owner-only (0o600),
    # closing the TOCTOU window between bind() and chmod().
    old_umask = os.umask(0o177)
    try:
        server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_sock.bind(sock_path)
    finally:
        os.umask(old_umask)
    server_sock.listen(100)

    _logger.warning("Terminal broker started (pid=%d) on %s", os.getpid(), sock_path)

    threading.Thread(target=_cleanup_loop, daemon=True).start()

    try:
        while True:
            try:
                conn, _ = server_sock.accept()
                threading.Thread(
                    target=_handle_client,
                    args=(conn,),
                    daemon=True,
                ).start()
            except OSError:
                break
    finally:
        server_sock.close()
        try:
            os.unlink(sock_path)
        except FileNotFoundError:
            _logger.debug("Broker socket already removed on shutdown: %s", sock_path)
        lock_fd.close()


if __name__ == "__main__":
    main()
