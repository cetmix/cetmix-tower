# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from odoo.exceptions import ValidationError

from .common import TestTowerTerminalCommon


class TestTowerTerminalSession(TestTowerTerminalCommon):
    """Validate terminal session lifecycle and input guards."""

    def test_action_open_for_server(self):
        """Create a session from server and return client action."""
        with self._patch_broker_call(), self._patch_start_pusher():
            action = self.TerminalSession.action_open_for_server(self.server_test_1.id)

        session = self.TerminalSession.browse(action["params"]["session_id"])
        self.assertTrue(session.exists(), "Session must be created")
        self.assertEqual(action["tag"], "cetmix_tower_server_terminal.terminal")
        self.assertEqual(session.state, "open")
        self.assertIn("session_token", action["params"])

    def test_action_open_for_server_not_found(self):
        """Opening a session for a nonexistent server raises ValidationError."""
        with self.assertRaises(ValidationError):
            self.TerminalSession.action_open_for_server(0)

    def test_state_selection_and_default(self):
        """State field must keep expected values and default to 'open'."""
        values = self.TerminalSession._selection_state()
        self.assertIn(("open", "Open"), values)
        self.assertIn(("closed", "Closed"), values)
        self.assertIn(("error", "Error"), values)

        session = self._create_open_session()
        self.assertEqual(session.state, "open")

    def test_terminal_send_validation(self):
        """Reject non-string and oversized payloads before broker call."""
        session = self._create_open_session()

        with self.assertRaises(ValidationError):
            session.terminal_send(False)

        with self.assertRaises(ValidationError):
            session.terminal_send("x" * (session._MAX_PAYLOAD_LENGTH + 1))

    def test_terminal_resize_sanitization(self):
        """Resize payload sent to broker must be clamped to allowed bounds."""
        session = self._create_open_session()

        with patch(
            "odoo.addons.cetmix_tower_server_terminal.models."
            "cx_tower_terminal_session.CxTowerTerminalSession._broker_call",
            autospec=True,
            return_value={"state": "open", "output": "", "message": False},
        ) as broker_call:
            session.terminal_resize(1, 999)

        _, request = broker_call.call_args.args
        self.assertEqual(request["cols"], session._MIN_TERMINAL_COLS)
        self.assertEqual(request["rows"], session._MAX_TERMINAL_ROWS)

    def test_terminal_close(self):
        """Closing a session must persist closed state and message."""
        session = self._create_open_session()

        with self._patch_broker_call(), self._patch_stop_pusher():
            response = session.terminal_close()

        self.assertEqual(response["state"], "closed")
        self.assertEqual(session.state, "closed")
        self.assertTrue(session.message)

    def test_terminal_read_restarts_pusher(self):
        """terminal_read restarts the output pusher when session is open."""
        session = self._create_open_session()

        with self._patch_broker_call(
            return_value={"state": "open", "output": "banner", "message": False}
        ), self._patch_start_pusher() as mock_pusher:
            response = session.terminal_read()

        self.assertEqual(response["state"], "open")
        self.assertEqual(response["output"], "banner")
        mock_pusher.assert_called_once()

    def test_terminal_send_valid_payload(self):
        """A valid string payload is forwarded to the broker."""
        session = self._create_open_session()

        with patch(
            "odoo.addons.cetmix_tower_server_terminal.models."
            "cx_tower_terminal_session.CxTowerTerminalSession._broker_call",
            autospec=True,
            return_value={"state": "open", "output": "", "message": False},
        ) as broker_call:
            session.terminal_send("ls -la\n")

        _, request = broker_call.call_args.args
        self.assertEqual(request["action"], "send")
        self.assertEqual(request["payload"], "ls -la\n")

    def test_terminal_reconnect(self):
        """terminal_reconnect closes the old session and opens a new one."""
        session = self._create_open_session()

        with self._patch_broker_call(
            return_value={"state": "open", "output": "", "message": False}
        ), self._patch_stop_pusher(), self._patch_start_pusher():
            response = session.terminal_reconnect()

        self.assertEqual(response["state"], "open")

