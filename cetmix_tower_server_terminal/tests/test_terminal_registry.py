# Copyright Cetmix OÜ 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json
import time
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tools import mute_logger

from ..constants import (
    ACTION_CLOSE,
    ACTION_INPUT,
    ACTION_RESIZE,
    DETACHED_GRACE,
    MAX_OUTPUT_CHUNK,
    OUTPUT_FLUSH_IDLE,
    OUTPUT_SMALL_ENOUGH,
    STATE_CLOSED,
    STATE_ERROR,
)
from ..tools import terminal_registry
from .common import (
    EndlessShell,
    FakeConnection,
    FakeShell,
    TestTowerTerminalCommon,
)

REGISTRY = "odoo.addons.cetmix_tower_server_terminal.tools.terminal_registry"


@tagged("post_install", "-at_install")
class TestTerminalRegistry(TestTowerTerminalCommon):
    """The part of a session that lives in the process, not in the database."""

    def _build_session(self, output=""):
        """Return a session with a fake shell and no thread of its own.

        Args:
            output (str): Output the fake shell returns once.

        Returns:
            terminal_registry.TerminalSession: Session ready to be driven by the
                test, with its publications collected in `self.published`.
        """
        record = self.open_session()
        session = terminal_registry.TerminalSession(record)
        session.shell = FakeShell(output)
        self.published = []

        def publish(output="", state=None, message=None):
            self.published.append({"output": output, "state": state})
            # The real one says whether the bus took it, and the flush keeps
            # what did not go out.
            return True

        session._publish = publish
        session._write_record = lambda state, message: True
        return session

    # -- the registry itself

    def test_a_session_is_started_once(self):
        """Subscribing twice to the same channel does not open a second shell."""
        record = self.open_session()
        websocket = object()
        with (
            patch(f"{REGISTRY}.TerminalSession.start") as start,
            patch(f"{REGISTRY}._ensure_listener"),
        ):
            session = terminal_registry.ensure_session(record, websocket)
            again = terminal_registry.ensure_session(record, websocket)
        self.addCleanup(terminal_registry._unregister, session)
        self.assertIs(again, session)
        start.assert_called_once()
        self.assertIs(terminal_registry.get_session(record.session_token), session)

    def test_a_websocket_that_comes_back_finds_its_session(self):
        """A reconnection attaches to the live shell instead of losing it.

        The websocket of a browser can drop and be replaced while the shell is
        perfectly alive. The replacement subscribes to the same channel, and
        has to end up attached to the session that is already running here.
        """
        record = self.open_session()
        first, second = object(), object()
        with (
            patch(f"{REGISTRY}.TerminalSession.start"),
            patch(f"{REGISTRY}._ensure_listener"),
        ):
            session = terminal_registry.ensure_session(record, first)
        self.addCleanup(terminal_registry._unregister, session)

        terminal_registry.detach_websocket(first)
        self.assertTrue(session._detached_since)
        self.assertTrue(
            terminal_registry.attach_websocket(record.session_token, second)
        )
        self.assertFalse(
            session._detached_since, "Coming back cancels the grace period"
        )
        self.assertIn(second, session.websockets)

    def test_attaching_a_session_of_another_process(self):
        """A token this process knows nothing about is not attached to."""
        self.assertFalse(terminal_registry.attach_websocket("nope", object()))

    def test_a_session_waits_for_the_browser_to_come_back(self):
        """Losing the last websocket starts a grace period instead of closing."""
        record = self.open_session()
        websocket = object()
        with (
            patch(f"{REGISTRY}.TerminalSession.start"),
            patch(f"{REGISTRY}._ensure_listener"),
        ):
            session = terminal_registry.ensure_session(record, websocket)
        self.addCleanup(terminal_registry._unregister, session)

        terminal_registry.detach_websocket(websocket)
        self.assertTrue(session._detached_since, "The grace period must have started")
        session.attach(websocket)
        self.assertFalse(session._detached_since, "Coming back must cancel it")

    def test_notifications_of_other_processes_are_ignored(self):
        """A notification about a session of another process changes nothing."""
        terminal_registry._handle_notification('{"token": "nope", "action": "input"}')

    def test_notifications_are_dispatched_in_arrival_order(self):
        """What arrives in one poll reaches the shell as it was typed.

        A command and the Enter that runs it can land in the same poll, so the
        order the listener consumes them in is the order the user sees. The
        queue is handed over whole, the way the listener gets it from postgres,
        so this fails if it is ever drained from the wrong end again.
        """
        session = self._build_session()
        terminal_registry._SESSIONS[session.token] = session
        self.addCleanup(terminal_registry._unregister, session)

        connection = FakeConnection(
            [
                json.dumps(
                    {"token": session.token, "action": ACTION_INPUT, "data": piece}
                )
                for piece in ("whoami", "\n")
            ]
        )
        terminal_registry._consume_notifications(connection)
        self.assertEqual(session.shell.sent, ["whoami", "\n"])
        self.assertEqual(connection.notifies, [], "The queue has to be drained")

    @mute_logger(REGISTRY)
    def test_malformed_notifications_are_ignored(self):
        """A notification that is not json is dropped instead of raising."""
        terminal_registry._handle_notification("not json")

    # -- actions

    def test_input_reaches_the_shell(self):
        """What the user typed is written to the shell."""
        session = self._build_session()
        session.handle_action({"action": ACTION_INPUT, "data": "ls -la\n"})
        self.assertEqual(session.shell.sent, ["ls -la\n"])

    def test_empty_input_is_not_sent(self):
        """An empty payload is not written to the shell."""
        session = self._build_session()
        session.handle_action({"action": ACTION_INPUT, "data": ""})
        self.assertEqual(session.shell.sent, [])

    def test_resize_reaches_the_shell(self):
        """The new window size is applied to the remote pseudo terminal."""
        session = self._build_session()
        session.handle_action({"action": ACTION_RESIZE, "cols": 120, "rows": 40})
        self.assertEqual(session.shell.size, (120, 40))

    def test_close_asks_the_session_to_stop(self):
        """A close action stops the session with the state it was given."""
        session = self._build_session()
        session.handle_action({"action": ACTION_CLOSE, "message": "Bye"})
        self.assertTrue(session._stop.is_set())
        self.assertEqual(session._closing_state, STATE_CLOSED)
        self.assertEqual(session._closing_message, "Bye")

    @mute_logger(REGISTRY)
    def test_unknown_actions_are_ignored(self):
        """An action the session does not know about is logged, not run."""
        session = self._build_session()
        session.handle_action({"action": "dance"})
        self.assertEqual(session.shell.sent, [])
        self.assertFalse(session._stop.is_set())

    @mute_logger(REGISTRY)
    def test_a_broken_shell_ends_the_session(self):
        """A shell that cannot be written to ends the session with an error."""
        session = self._build_session()
        session.shell.send_error = OSError("channel closed")
        session.handle_action({"action": ACTION_INPUT, "data": "ls\n"})
        self.assertTrue(session._stop.is_set())
        self.assertEqual(session._closing_state, STATE_ERROR)

    # -- output

    def test_output_that_never_stops_does_not_outlive_the_browser(self):
        """A shell that keeps writing is still closed once nobody is watching.

        The detach check used to live after the read, so output that never
        paused kept the loop from ever reaching it and the session outlived
        the browser that had left.
        """
        session = self._build_session()
        session.shell = EndlessShell()
        session._get_idle_timeout = lambda: 3600
        session._write_record = lambda state, message: True
        session._detached_since = time.monotonic() - DETACHED_GRACE - 1
        session._pump()
        self.assertEqual(session.state, STATE_CLOSED)

    def test_a_small_echo_goes_out_at_once(self):
        """What a keystroke echoes back is not worth grouping.

        Waiting for the idle window to close costs that window on every
        character somebody types, which is what makes a terminal feel slow.
        """
        session = self._build_session()
        session._buffer = "x"
        session._buffer_since = time.monotonic()
        session._last_output_at = time.monotonic()
        session._flush()
        self.assertEqual([entry["output"] for entry in self.published], ["x"])

    def test_a_burst_waits_for_the_shell_to_go_quiet(self):
        """Output large enough to be a burst is grouped, not sent per chunk."""
        session = self._build_session()
        burst = "x" * (OUTPUT_SMALL_ENOUGH + 1)
        session._buffer = burst
        session._buffer_since = time.monotonic()
        session._last_output_at = time.monotonic()
        session._flush()
        self.assertEqual(self.published, [], "A burst must not be published mid flight")

        session._last_output_at = time.monotonic() - OUTPUT_FLUSH_IDLE - 0.01
        session._flush()
        self.assertEqual([entry["output"] for entry in self.published], [burst])
        self.assertFalse(session._buffer, "The buffer must be emptied once published")

    def test_output_larger_than_a_notification_is_split(self):
        """A burst too large for one notification is published in several."""
        session = self._build_session()
        session._buffer = "x" * (MAX_OUTPUT_CHUNK * 2 + 5)
        session._buffer_since = time.monotonic()
        session._flush(force=True)
        self.assertEqual(len(self.published), 3)
        self.assertTrue(
            all(len(entry["output"]) <= MAX_OUTPUT_CHUNK for entry in self.published),
            "No notification may be larger than the chunk size",
        )

    def test_nothing_to_publish(self):
        """An empty buffer publishes nothing, forced or not."""
        session = self._build_session()
        session._flush(force=True)
        self.assertEqual(self.published, [])

    def test_the_end_of_a_session_is_published(self):
        """The last thing a session does is tell the browser it is over."""
        session = self._build_session()
        shell = session.shell
        # Registered on purpose: asserting that the session is gone proves
        # nothing unless it was there to begin with.
        terminal_registry._SESSIONS[session.token] = session
        self.addCleanup(terminal_registry._unregister, session)
        session._finish(STATE_CLOSED, "The remote shell was closed.")
        self.assertEqual(self.published[-1]["state"], STATE_CLOSED)
        self.assertTrue(shell.closed, "The shell must be closed with the session")
        self.assertIsNone(terminal_registry.get_session(session.token))
