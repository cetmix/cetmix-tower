# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError

from .common import TestTowerCommon


class TestTowerServerLog(TestTowerCommon):
    """Test the cx.tower.server.log model access rights."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test server logs with specific users
        cls.server_log_1 = (
            cls.ServerLog.with_user(cls.user)
            .sudo()
            .create(
                {
                    "name": "Test Log 1",
                    "server_id": cls.server_test_1.id,
                    "log_type": "file",
                    "access_level": "1",
                }
            )
        )

        cls.server_log_2 = (
            cls.ServerLog.with_user(cls.manager)
            .sudo()
            .create(
                {
                    "name": "Test Log 2",
                    "server_id": cls.server_test_1.id,
                    "log_type": "file",
                    "access_level": "1",
                }
            )
        )

        # Create additional server for testing
        cls.server_2 = cls.Server.create(
            {
                "name": "Test Server 2",
                "ip_v4_address": "localhost",
                "ssh_username": "test2",
                "ssh_password": "test2",
                "ssh_port": 22,
                "user_ids": [(6, 0, [])],
                "manager_ids": [(6, 0, [])],
            }
        )

    def test_user_access(self):
        """Test user access to server logs"""
        # Add user to server's user_ids
        self.server_test_1.write(
            {
                "user_ids": [(6, 0, [self.user.id])],
            }
        )

        # Case 1: User should be able to read when:
        # - access_level == "1"
        # - user is in server's user_ids
        recs = self.ServerLog.with_user(self.user).search(
            [("id", "in", [self.server_log_1.id, self.server_log_2.id])]
        )
        self.assertEqual(
            len(recs),
            2,
            "User should be able to read all logs with access_level '1'"
            " when in user_ids",
        )

        # Case 2: User should not be able to read when not in server's user_ids
        self.server_test_1.write(
            {
                "user_ids": [(5, 0, 0)],  # Remove all users
            }
        )
        recs = self.ServerLog.with_user(self.user).search(
            [("id", "=", self.server_log_1.id)]
        )
        self.assertEqual(
            len(recs),
            0,
            "User should not be able to read when not in server's user_ids",
        )

        # Case 3: User should not be able to read when access_level > "1"
        self.server_test_1.write(
            {
                "user_ids": [(6, 0, [self.user.id])],
            }
        )
        high_access_log = (
            self.ServerLog.with_user(self.user)
            .sudo()
            .create(
                {
                    "name": "High Access Log",
                    "server_id": self.server_test_1.id,
                    "log_type": "file",
                    "access_level": "2",
                }
            )
        )

        recs = self.ServerLog.with_user(self.user).search(
            [("id", "=", high_access_log.id)]
        )
        self.assertEqual(
            len(recs),
            0,
            "User should not be able to read logs with access_level > '1'",
        )

    def test_manager_access(self):
        """Test manager access to server logs"""
        # Add manager to server's manager_ids
        self.server_test_1.write(
            {
                "manager_ids": [(6, 0, [self.manager.id])],
            }
        )

        # Case 1: Manager should be able to read when:
        # - access_level <= "2"
        # - manager is in server's manager_ids
        recs = self.ServerLog.with_user(self.manager).search(
            [("id", "in", [self.server_log_1.id, self.server_log_2.id])]
        )
        self.assertEqual(
            len(recs),
            2,
            "Manager should be able to read all logs when in manager_ids",
        )

        # Case 2: Manager should be able to create and write when:
        # - access_level <= "2"
        # - manager is in server's manager_ids
        try:
            new_log = self.ServerLog.with_user(self.manager).create(
                {
                    "name": "Manager Test Log",
                    "server_id": self.server_test_1.id,
                    "log_type": "file",
                    "access_level": "2",
                }
            )
        except AccessError:
            self.fail(
                "Manager should be able to create logs when in server's manager_ids"
            )

        try:
            new_log.write({"name": "Updated Name"})
        except AccessError:
            self.fail(
                "Manager should be able to write logs when in server's manager_ids"
            )
        self.assertEqual(new_log.name, "Updated Name")

        # Case 3: Manager should be able to unlink when:
        # - access_level <= "2"
        # - created by manager
        # - manager is in server's manager_ids
        try:
            new_log.unlink()
        except AccessError:
            self.fail(
                "Manager should be able to unlink own logs when in server's manager_ids"
            )

        # Case 4: Manager should not be able to unlink logs created by others
        with self.assertRaises(AccessError):
            self.server_log_1.with_user(self.manager).unlink()

        # Case 5: Manager should not be able to access logs with access_level > "2"
        high_access_log = (
            self.ServerLog.with_user(self.manager)
            .sudo()
            .create(
                {
                    "name": "High Access Log",
                    "server_id": self.server_test_1.id,
                    "log_type": "file",
                    "access_level": "3",
                }
            )
        )

        recs = self.ServerLog.with_user(self.manager).search(
            [("id", "=", high_access_log.id)]
        )
        self.assertEqual(
            len(recs),
            0,
            "Manager should not be able to read logs with access_level > '2'",
        )

    def test_root_access(self):
        """Test root user unrestricted access"""
        # Create test logs with various conditions
        test_logs = self.ServerLog.with_user(self.root).create(
            [
                {
                    "name": f"Root Test Log {level}",
                    "server_id": self.server_test_1.id,
                    "log_type": "file",
                    "access_level": level,
                }
                for level in ["1", "2", "3"]
            ]
        )

        # Root should be able to read all logs regardless of conditions
        recs = self.ServerLog.with_user(self.root).search([("id", "in", test_logs.ids)])
        self.assertEqual(
            len(recs),
            3,
            "Root should have unrestricted read access to all logs",
        )

        # Root should be able to write all logs
        try:
            for log in test_logs:
                log.write({"name": "Updated by Root"})
        except AccessError:
            self.fail("Root should be able to write any logs")

        # Root should be able to unlink all logs
        try:
            test_logs.unlink()
        except AccessError:
            self.fail("Root should be able to unlink any logs")

    def test_log_text_access_restrictions(self):
        """Test log_text field access controls"""
        test_log = self.ServerLog.create(
            {
                "name": "Access Test Log",
                "server_id": self.server_test_1.id,
                "log_type": "file",
                "access_level": "1",
                "log_text": "<p>Test content</p>",
            }
        )

        # 1. Verify read access for all roles
        for user in (self.root, self.manager, self.user):
            content = test_log.with_user(user).log_text
            self.assertEqual(
                content, "<p>Test content</p>", f"{user.name} should read log_text"
            )

        # 2. Verify write prohibition for all roles
        for user in (self.root, self.manager, self.user):
            with self.assertRaises(
                AccessError, msg=f"{user.name} shouldn't modify log_text"
            ):
                test_log.with_user(user).write({"log_text": "<p>Modified</p>"})

    def test_log_text_refresh_mechanism(self):
        """Test log_text can only be updated via refresh action"""
        test_log = self.ServerLog.sudo().create(
            {
                "name": "Refresh Test Log",
                "server_id": self.server_test_1.id,
                "log_type": "file",
                "access_level": "1",
                "log_text": "<p>Initial</p>",
            }
        )

        # 1. Direct write attempts should fail
        with self.assertRaises(AccessError):
            test_log.sudo().write({"log_text": "<p>Illegal Update</p>"})

        # 2. Verify refresh action updates content
        original_content = test_log.log_text
        test_log.action_update_log()

        self.assertNotEqual(
            test_log.log_text,
            original_content,
            "action_update_log() should update log_text",
        )

    def test_log_text_copy(self):
        """Duplicating a log must NOT keep the log output"""
        original = self.ServerLog.create(
            {
                "name": "Original Log",
                "server_id": self.server_test_1.id,
                "log_type": "file",
                "access_level": "1",
                "log_text": "<p>Original content</p>",
            }
        )

        copied = original.copy()

        # log_text must be cleared because copy=False
        self.assertFalse(copied.log_text, "Copied log must not keep log_text")
        self.assertNotEqual(copied.id, original.id)
        self.assertTrue(bool(copied.name))
