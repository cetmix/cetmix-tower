# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields
from odoo.exceptions import AccessError

from .common import TestTowerCommon


class TestTowerPlanLog(TestTowerCommon):
    """Test the cx.tower.plan.log model access rights."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create plans with different access levels
        cls.plan_level_1 = cls.Plan.create(
            {
                "name": "Test Plan L1",
                "access_level": "1",
            }
        )

        cls.plan_level_2 = cls.Plan.create(
            {
                "name": "Test Plan L2",
                "access_level": "2",
            }
        )

        cls.plan_level_3 = cls.Plan.create(
            {
                "name": "Test Plan L3",
                "access_level": "3",
            }
        )

        # Create test plan logs with specific users
        cls.plan_log_1 = (
            cls.PlanLog.with_user(cls.user)
            .sudo()
            .create(
                {
                    "server_id": cls.server_test_1.id,
                    "plan_id": cls.plan_level_1.id,
                    "start_date": fields.Datetime.now(),
                }
            )
        )

        cls.plan_log_2 = (
            cls.PlanLog.with_user(cls.manager)
            .sudo()
            .create(
                {
                    "server_id": cls.server_test_1.id,
                    "plan_id": cls.plan_level_1.id,
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
        """Test user read access to plan logs"""
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
        recs = self.PlanLog.with_user(self.user).search(
            [("id", "in", [self.plan_log_1.id, self.plan_log_2.id])]
        )
        self.assertEqual(
            len(recs),
            1,
            "User should only be able to read their own logs",
        )
        self.assertIn(
            self.plan_log_1,
            recs,
            "User should be able to read own logs when conditions are met",
        )
        self.assertNotIn(
            self.plan_log_2,
            recs,
            "User should not be able to read logs created by others",
        )

        # Case 2: User should not be able to read when not in server's user_ids
        self.server_test_1.write(
            {
                "user_ids": [(5, 0, 0)],  # Remove all users
            }
        )
        recs = self.PlanLog.with_user(self.user).search(
            [("id", "=", self.plan_log_1.id)]
        )
        self.assertNotIn(
            self.plan_log_1,
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
            self.PlanLog.with_user(self.user)
            .sudo()
            .create(
                {
                    "server_id": self.server_test_1.id,
                    "plan_id": self.plan_level_2.id,
                    "start_date": fields.Datetime.now(),
                }
            )
        )
        recs = self.PlanLog.with_user(self.user).search(
            [("id", "=", high_access_log.id)]
        )
        self.assertNotIn(
            high_access_log,
            recs,
            "User should not be able to read logs with access_level > '1'"
            " even if created by them",
        )

    def test_manager_read_access(self):
        """Test manager read access to plan logs"""
        # Case 1: Manager should be able to read when:
        # - access_level <= "2"
        # - manager is in server's manager_ids
        self.server_test_1.write(
            {
                "manager_ids": [(6, 0, [self.manager.id])],
            }
        )
        recs = self.PlanLog.with_user(self.manager).search(
            [("id", "in", [self.plan_log_1.id, self.plan_log_2.id])]
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
        recs = self.PlanLog.with_user(self.manager).search(
            [("id", "in", [self.plan_log_1.id, self.plan_log_2.id])]
        )
        self.assertEqual(
            len(recs),
            2,
            "Manager should be able to read all logs when in server's user_ids",
        )

        # Case 3: Manager should not be able to read when access_level > "2"
        high_access_log = (
            self.PlanLog.with_user(self.manager)
            .sudo()
            .create(
                {
                    "server_id": self.server_test_1.id,
                    "plan_id": self.plan_level_3.id,
                    "start_date": fields.Datetime.now(),
                }
            )
        )
        recs = self.PlanLog.with_user(self.manager).search(
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
        recs = self.PlanLog.with_user(self.manager).search(
            [("id", "in", [self.plan_log_1.id, self.plan_log_2.id])]
        )
        self.assertNotIn(
            self.plan_log_1,
            recs,
            "Manager should not be able to read logs when he is not"
            " in users_ids or manager_ids",
        )

    def test_root_read_only_access(self):
        """Root can read all plan logs, but cannot create/modify/delete"""
        # Create test logs with sudo()
        test_logs = self.PlanLog.sudo().create(
            [
                {
                    "server_id": self.server_2.id,
                    "plan_id": plan.id,
                    "start_date": fields.Datetime.now(),
                }
                for plan in [self.plan_level_1, self.plan_level_2, self.plan_level_3]
            ]
        )

        # Root should be able to read all logs regardless of:
        # - access_level
        # - server relationships
        # - who created them
        recs = self.PlanLog.with_user(self.root).search([("id", "in", test_logs.ids)])
        self.assertEqual(
            len(recs),
            3,
            "Root should have unrestricted read access to all logs",
        )

        # Root can't create logs
        with self.assertRaises(AccessError):
            self.PlanLog.with_user(self.root).create(
                {
                    "server_id": self.server_2.id,
                    "plan_id": self.plan_level_1.id,
                    "start_date": fields.Datetime.now(),
                }
            )

        # Root cannot modify logs
        with self.assertRaises(AccessError):
            test_logs.with_user(self.root).write({"start_date": fields.Datetime.now()})

        # Root cannot delete logs
        with self.assertRaises(AccessError):
            test_logs.with_user(self.root).unlink()

        # Test read on all records
        all_recs = self.PlanLog.with_user(self.root).search([])
        self.assertGreater(
            len(all_recs),
            0,
            "Root should be able to read all plan logs",
        )
