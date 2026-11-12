# Copyright Cetmix OÜ 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import TestTowerTerminalCommon


@tagged("post_install", "-at_install")
class TestTerminalSecurity(TestTowerTerminalCommon):
    """Who may open a terminal, and who may look at someone else's."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.other_manager = cls.Users.create(
            {
                "name": "Test Manager 2",
                "login": "test_manager_2",
                "email": "test_manager_2@example.com",
                "groups_id": [
                    (6, 0, [cls.group_manager.id, cls.env.ref("base.group_user").id])
                ],
            }
        )
        cls.server_test_1.write({"manager_ids": [(4, cls.other_manager.id)]})

    def test_manager_opens_a_terminal(self):
        """A manager of the server opens a terminal and reads their session."""
        session = self.open_session(user=self.manager)
        self.assertTrue(session.with_user(self.manager).session_token)

    def test_user_cannot_open_a_terminal(self):
        """A plain Tower user cannot open a terminal, even on a server they see."""
        self.server_test_1.write({"user_ids": [(4, self.user.id)]})
        with self.assertRaises(AccessError):
            self.open_session(user=self.user)

    def test_manager_without_access_to_the_server_cannot_open_a_terminal(self):
        """Opening a terminal needs access to the server it runs on."""
        server = self.Server.create(
            {
                "name": "Test No Access",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "host_key": "test_key",
                "os_id": self.os_debian_10.id,
            }
        )
        with self.assertRaises(AccessError):
            self.open_session(user=self.manager, server=server)

    def test_a_session_cannot_be_created_on_a_server_out_of_reach(self):
        """Creating the record directly does not bypass the server rules.

        The shell reads the credentials of the server with `sudo()`, so the
        right to use it cannot be checked only in the action that opens it.
        """
        server = self.Server.create(
            {
                "name": "Test Out Of Reach",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "host_key": "test_key",
                "os_id": self.os_debian_10.id,
            }
        )
        with self.assertRaises(AccessError):
            self.TerminalSession.with_user(self.manager).create(
                {"name": "Sneaky", "server_id": server.id}
            )

    def test_a_session_cannot_be_moved_to_a_server_out_of_reach(self):
        """The same check applies when the server of a session is changed."""
        session = self.open_session(user=self.manager)
        server = self.Server.create(
            {
                "name": "Test Out Of Reach 2",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "host_key": "test_key",
                "os_id": self.os_debian_10.id,
            }
        )
        with self.assertRaises(AccessError):
            session.with_user(self.manager).write({"server_id": server.id})

    def test_access_revoked_before_the_shell_opens_stops_the_connection(self):
        """A session opened before access was revoked does not reach the host.

        The session record can sit unopened while an administrator takes the
        server away, and the credentials behind it are read with `sudo()`, so
        the check has to happen where the shell is about to be opened.
        """
        session = self.open_session(user=self.manager)
        server = self.server_test_1.with_user(self.manager)
        self.assertTrue(
            server._get_terminal_connection_values(),
            "A manager of the server gets what the shell needs",
        )

        self.server_test_1.write({"manager_ids": [(3, self.manager.id)]})
        self.server_test_1.invalidate_recordset()
        with self.assertRaises(AccessError):
            self.server_test_1.with_user(self.manager)._get_terminal_connection_values()
        self.assertTrue(session.exists(), "The record outlives the access")

    def test_a_session_is_private_to_the_user_who_opened_it(self):
        """Another manager neither finds nor reads a session that is not theirs."""
        session = self.open_session(user=self.manager)
        self.assertFalse(
            self.TerminalSession.with_user(self.other_manager).search(
                [("id", "=", session.id)]
            ),
            "A session of another user must not even be found",
        )
        with self.assertRaises(AccessError):
            session.with_user(self.other_manager).read(["session_token"])

    def test_root_does_not_read_sessions_of_other_users_either(self):
        """The rule is global, as it is for every Tower wizard.

        See `cetmix_tower_server/security/cx_tower_server_wizard_access_rules.xml`:
        a record that only exists to serve one user of one browser is of no use
        to anybody else, root included.
        """
        session = self.open_session(user=self.manager)
        with self.assertRaises(AccessError):
            session.with_user(self.root).read(["session_token"])
