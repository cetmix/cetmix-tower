# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError

from .common import TestTowerTerminalCommon


class TestTowerTerminalSecurity(TestTowerTerminalCommon):
    """Tests for terminal session access control rules."""

    def test_user_can_read_own_session(self):
        """A user can read terminal sessions they created."""
        session = self.TerminalSession.with_user(self.user).create(
            {
                "name": "Terminal: Test",
                "server_id": self.server_test_1.id,
            }
        )
        # Should not raise
        session.with_user(self.user).read(["state"])

    def test_user_cannot_read_other_session(self):
        """A user cannot read terminal sessions created by another user."""
        session = self.TerminalSession.with_user(self.user).create(
            {
                "name": "Terminal: Test",
                "server_id": self.server_test_1.id,
            }
        )
        user_bob_env = self.TerminalSession.with_user(self.user_bob)
        with self.assertRaises(AccessError):
            user_bob_env.browse(session.id).read(["state"])

    def test_bus_channel_uses_token_not_id(self):
        """The bus channel name is based on session_token, not session integer id."""
        session = self._create_open_session()
        self.assertNotEqual(session.session_token, str(session.id))
        # The pusher thread uses session_token as channel name (verified by
        # checking _get_client_action returns session_token in params)
        action = session._get_client_action()
        self.assertIn("session_token", action["params"])
        self.assertEqual(action["params"]["session_token"], session.session_token)
