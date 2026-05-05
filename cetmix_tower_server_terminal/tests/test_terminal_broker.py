# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import MagicMock, patch

from odoo.exceptions import ValidationError

from .common import TestTowerTerminalCommon


class TestTowerTerminalBroker(TestTowerTerminalCommon):
    """Tests for broker IPC interaction: open, close, error handling."""

    def test_open_broker_session_success(self):
        """_open_broker_session persists open state on broker success."""
        session = self._create_open_session()

        with (
            self._patch_broker_call(return_value={"status": "ok"}),
            self._patch_start_pusher(),
        ):
            session._open_broker_session()

        self.assertEqual(session.state, "open")
        self.assertFalse(session.message)

    def test_open_broker_session_broker_error(self):
        """_open_broker_session raises ValidationError when broker returns error."""
        session = self._create_open_session()

        raised = False
        try:
            with (
                self._patch_broker_call(
                    return_value={"status": "error", "message": "SSH refused"}
                ),
                self._patch_start_pusher(),
                patch(
                    "odoo.addons.cetmix_tower_server_terminal.models."
                    "cx_tower_terminal_session._logger"
                ),
            ):
                session._open_broker_session()
        except ValidationError:
            raised = True

        self.assertTrue(raised, "Expected ValidationError to be raised")
        # State must be persisted to DB before the exception propagates.
        # Use try/except (not assertRaises) to avoid Odoo's savepoint rollback
        # that UserError-catching assertRaises applies.
        self.assertEqual(session.state, "error")

    def test_open_broker_session_exception(self):
        """_open_broker_session wraps unexpected exceptions in ValidationError."""
        session = self._create_open_session()

        raised = False
        try:
            with (
                patch(
                    "odoo.addons.cetmix_tower_server_terminal.models."
                    "cx_tower_terminal_session.CxTowerTerminalSession._broker_call",
                    autospec=True,
                    side_effect=RuntimeError("Broker unavailable"),
                ),
                patch(
                    "odoo.addons.cetmix_tower_server_terminal.models."
                    "cx_tower_terminal_session._logger"
                ),
            ):
                session._open_broker_session()
        except ValidationError:
            raised = True

        self.assertTrue(raised, "Expected ValidationError to be raised")
        self.assertEqual(session.state, "error")

    def test_broker_call_retries_on_failure(self):
        """_broker_call retries once and calls _ensure_broker on first OSError."""
        session = self._create_open_session()

        with (
            patch(
                "odoo.addons.cetmix_tower_server_terminal.models."
                "cx_tower_terminal_session.socket.socket",
            ) as mock_sock_cls,
            patch(
                "odoo.addons.cetmix_tower_server_terminal.models."
                "cx_tower_terminal_session.CxTowerTerminalSession._ensure_broker",
                autospec=True,
            ) as mock_ensure,
        ):
            # First attempt raises OSError; second returns a valid response
            sock_fail = MagicMock()
            sock_fail.__enter__ = MagicMock(side_effect=OSError("conn refused"))
            sock_fail.__exit__ = MagicMock(return_value=False)
            sock_ok = MagicMock()
            sock_ok.__enter__ = MagicMock(return_value=sock_ok)
            sock_ok.__exit__ = MagicMock(return_value=False)
            sock_ok.makefile.return_value.readline.return_value = '{"status": "ok"}\n'
            mock_sock_cls.side_effect = [sock_fail, sock_ok]

            result = session._broker_call({"action": "ping", "token": "abc"})

        mock_ensure.assert_called_once()
        self.assertEqual(result.get("status"), "ok")

    def test_sanitize_terminal_size_invalid_type(self):
        """Non-numeric terminal size raises ValidationError."""
        session = self._create_open_session()
        with self.assertRaises(ValidationError):
            session._sanitize_terminal_size("wide", "tall")

    def test_sanitize_terminal_size_clamping(self):
        """Terminal size is clamped to allowed min/max bounds."""
        session = self._create_open_session()
        cols, rows = session._sanitize_terminal_size(0, 9999)
        self.assertEqual(cols, session._MIN_TERMINAL_COLS)
        self.assertEqual(rows, session._MAX_TERMINAL_ROWS)

    def test_sanitize_read_timeout(self):
        """Read timeout is clamped to [0, 2] seconds."""
        session = self._create_open_session()
        self.assertEqual(session._sanitize_read_timeout({"read_timeout": 999}), 2.0)
        self.assertEqual(session._sanitize_read_timeout({"read_timeout": -1}), 0.0)
        self.assertEqual(session._sanitize_read_timeout(None), 0.0)
        self.assertEqual(session._sanitize_read_timeout("bad"), 0.0)

    def test_build_broker_open_request(self):
        """Broker open request contains expected fields from server config."""
        session = self._create_open_session()
        request = session._build_broker_open_request()
        self.assertEqual(request["action"], "open")
        self.assertEqual(request["token"], session.session_token)
        self.assertEqual(request["host"], self.server_test_1.ip_v4_address)
        self.assertEqual(request["port"], self.server_test_1.ssh_port)
