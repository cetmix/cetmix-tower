# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields
from odoo.exceptions import AccessError

from .common import TestTowerCommon


class TestTowerCommandLog(TestTowerCommon):
    """Test the cx.tower.command.log model access rights."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create commands with different access levels
        cls.command_level_1 = cls.Command.create(
            {
                "name": "Test Command L1",
                "action": "ssh_command",
                "access_level": "1",
            }
        )

        cls.command_level_2 = cls.Command.create(
            {
                "name": "Test Command L2",
                "action": "ssh_command",
                "access_level": "2",
            }
        )

        cls.command_level_3 = cls.Command.create(
            {
                "name": "Test Command L3",
                "action": "ssh_command",
                "access_level": "3",
            }
        )

        # Create test command logs with specific users
        cls.command_log_1 = (
            cls.CommandLog.with_user(cls.user)
            .sudo()
            .create(
                {
                    "server_id": cls.server_test_1.id,
                    "command_id": cls.command_level_1.id,
                    "start_date": fields.Datetime.now(),
                }
            )
        )

        cls.command_log_2 = (
            cls.CommandLog.with_user(cls.manager)
            .sudo()
            .create(
                {
                    "server_id": cls.server_test_1.id,
                    "command_id": cls.command_level_1.id,
                    "start_date": fields.Datetime.now(),
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

    def test_user_read_access(self):
        """Test user read access to command logs"""
        # Add user to server's user_ids to isolate creator check
        self.server_test_1.write(
            {
                "user_ids": [(6, 0, [self.user.id])],
            }
        )

        # Case 1: User should be able to read when:
        # - access_level == "1"
        # - created by user
        # - user is in server's user_ids
        recs = self.CommandLog.with_user(self.user).search(
            [("id", "in", [self.command_log_1.id, self.command_log_2.id])]
        )
        self.assertEqual(
            len(recs),
            1,
            "User should only be able to read their own logs",
        )
        self.assertIn(
            self.command_log_1,
            recs,
            "User should be able to read own logs when conditions are met",
        )
        self.assertNotIn(
            self.command_log_2,
            recs,
            "User should not be able to read logs created by others",
        )

        # Case 2: User should not be able to read when not in server's user_ids
        self.server_test_1.write(
            {
                "user_ids": [(5, 0, 0)],  # Remove all users
            }
        )
        recs = self.CommandLog.with_user(self.user).search(
            [("id", "=", self.command_log_1.id)]
        )
        self.assertNotIn(
            self.command_log_1,
            recs,
            "User should not be able to read when not in server's user_ids",
        )

        # Case 3: User should not be able to read when access_level > "1"
        self.server_test_1.write(
            {
                "user_ids": [(6, 0, [self.user.id])],
            }
        )
        high_access_log = (
            self.CommandLog.with_user(self.user)
            .sudo()
            .create(
                {
                    "server_id": self.server_test_1.id,
                    "command_id": self.command_level_2.id,  # Using command with access_level "2"  # noqa: E501
                    "start_date": fields.Datetime.now(),
                }
            )
        )
        recs = self.CommandLog.with_user(self.user).search(
            [("id", "=", high_access_log.id)]
        )
        self.assertNotIn(
            high_access_log,
            recs,
            "User should not be able to read logs with access_level > '1'"
            " even if created by them",
        )

    def test_manager_read_access(self):
        """Test manager read access to command logs"""
        # Case 1: Manager should be able to read when:
        # - access_level <= "2"
        # - manager is in server's manager_ids
        self.server_test_1.write(
            {
                "manager_ids": [(6, 0, [self.manager.id])],
            }
        )
        recs = self.CommandLog.with_user(self.manager).search(
            [("id", "in", [self.command_log_1.id, self.command_log_2.id])]
        )
        self.assertEqual(
            len(recs),
            2,
            "Manager should be able to read all logs when in server's manager_ids",
        )

        # Case 2: Manager should be able to read when in server's user_ids
        self.server_test_1.write(
            {
                "manager_ids": [(5, 0, 0)],  # Remove all managers
                "user_ids": [(6, 0, [self.manager.id])],
            }
        )
        recs = self.CommandLog.with_user(self.manager).search(
            [("id", "in", [self.command_log_1.id, self.command_log_2.id])]
        )
        self.assertEqual(
            len(recs),
            2,
            "Manager should be able to read all logs when in server's user_ids",
        )

        # Case 3: Manager should not be able to read when access_level > "2"
        high_access_log = (
            self.CommandLog.with_user(self.manager)
            .sudo()
            .create(
                {
                    "server_id": self.server_test_1.id,
                    "command_id": self.command_level_3.id,  # Using command with access_level "3"  # noqa: E501
                    "start_date": fields.Datetime.now(),
                }
            )
        )
        recs = self.CommandLog.with_user(self.manager).search(
            [("id", "=", high_access_log.id)]
        )
        self.assertNotIn(
            high_access_log,
            recs,
            "Manager should not be able to read logs with access_level > '2'",
        )

        # Case 4: Manager should not be able to read when he is not
        #  in users_ids or manager_ids
        self.server_test_1.write(
            {
                "user_ids": [(5, 0, 0)],
                "manager_ids": [(5, 0, 0)],
            }
        )
        recs = self.CommandLog.with_user(self.manager).search(
            [("id", "in", [self.command_log_1.id, self.command_log_2.id])]
        )
        self.assertNotIn(
            self.command_log_1,
            recs,
            "Manager should not be able to read logs when he is not"
            " in users_ids or manager_ids",
        )

    def test_root_read_only_access(self):
        """Root can read all command logs, but cannot create/modify/delete"""
        # Create test logs with sudo()
        test_logs = self.CommandLog.sudo().create(
            [
                {
                    "server_id": self.server_2.id,
                    "command_id": command.id,
                    "start_date": fields.Datetime.now(),
                }
                for command in [
                    self.command_level_1,
                    self.command_level_2,
                    self.command_level_3,
                ]
            ]
        )
        # Root cannot create logs
        with self.assertRaises(AccessError):
            self.CommandLog.with_user(self.root).create(
                {
                    "server_id": self.server_2.id,
                    "command_id": self.command_level_1.id,
                    "start_date": fields.Datetime.now(),
                }
            )

        # Root cannot modify logs
        with self.assertRaises(AccessError):
            test_logs.with_user(self.root).write({"start_date": fields.Datetime.now()})

        # Root cannot delete logs
        with self.assertRaises(AccessError):
            test_logs.with_user(self.root).unlink()

        # Root should be able to read all logs regardless of:
        # - access_level
        # - server relationships
        # - who created them
        recs = self.CommandLog.with_user(self.root).search(
            [("id", "in", test_logs.ids)]
        )
        self.assertEqual(
            len(recs),
            3,
            "Root should have unrestricted read access to all logs",
        )

        # Test read on all records
        all_recs = self.CommandLog.with_user(self.root).search([])
        self.assertGreater(
            len(all_recs),
            0,
            "Root should be able to read all command logs",
        )
