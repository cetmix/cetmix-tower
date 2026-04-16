# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from odoo.exceptions import ValidationError

from odoo.addons.cetmix_tower_server.tests.common import TestTowerCommon


class TestTowerTerminalSession(TestTowerCommon):
    """Validate terminal session lifecycle and input guards."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.TerminalSession = cls.env["cx.tower.terminal.session"]

    def _create_open_session(self):
        """Create an open terminal session bound to the common test server."""
        return self.TerminalSession.create(
            {
                "name": "Terminal: Test",
                "server_id": self.server_test_1.id,
            }
        )

    def test_action_open_for_server(self):
        """Create a session from server and return client action."""
        with (
            patch(
                "odoo.addons.cetmix_tower_server_terminal.models."
                "cx_tower_terminal_session.CxTowerTerminalSession._broker_call",
                autospec=True,
                return_value={"status": "ok"},
            ),
            patch(
                "odoo.addons.cetmix_tower_server_terminal.models."
                "cx_tower_terminal_session.CxTowerTerminalSession._start_output_pusher",
                autospec=True,
                return_value=None,
            ),
        ):
            action = self.TerminalSession.action_open_for_server(self.server_test_1.id)

        session = self.TerminalSession.browse(action["params"]["session_id"])
        self.assertTrue(session.exists(), "Session must be created")
        self.assertEqual(action["tag"], "cetmix_tower_server_terminal.terminal")
        self.assertEqual(session.state, "open")

    def test_state_selection_and_default(self):
        """State field must keep expected values and default."""
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

        with patch(
            "odoo.addons.cetmix_tower_server_terminal.models."
            "cx_tower_terminal_session.CxTowerTerminalSession._broker_call",
            autospec=True,
            return_value={"status": "ok"},
        ):
            response = session.terminal_close()

        self.assertEqual(response["state"], "closed")
        self.assertEqual(session.state, "closed")
        self.assertTrue(session.message)
