# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError

from .common import TestTowerCommon


class TestTowerPlanLineAction(TestTowerCommon):
    """Test the cx.tower.plan.line.action model access rights."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a test server
        cls.server = cls.Server.create(
            {
                "name": "Test Server",
                "ip_v4_address": "localhost",
                "ssh_username": "test",
                "ssh_password": "test",
                "ssh_port": 22,
                "user_ids": [(6, 0, [cls.user.id])],
                "manager_ids": [(6, 0, [cls.manager.id])],
            }
        )

        # Create a test plan with access level 1 for user tests
        cls.test_plan = cls.Plan.create(
            {
                "name": "Test Access Plan",
                "access_level": "1",
                "user_ids": [(6, 0, [cls.user.id])],
                "manager_ids": [(6, 0, [cls.manager.id])],
            }
        )

        # Create a test plan line
        cls.test_plan_line = cls.plan_line.create(
            {
                "plan_id": cls.test_plan.id,
                "command_id": cls.command_create_dir.id,
                "sequence": 10,
            }
        )

        # Create a test action
        cls.test_action = cls.plan_line_action.create(
            {
                "line_id": cls.test_plan_line.id,
                "condition": "==",
                "value_char": "0",
                "action": "n",
            }
        )

    def test_user_read_access(self):
        """Test user read access to plan line actions"""
        # Case 1: User should be able to read action when:
        # - access_level == "1"
        # - user is in plan's user_ids OR server's user_ids
        recs = self.plan_line_action.with_user(self.user).search(
            [("id", "=", self.test_action.id)]
        )
        self.assertIn(
            self.test_action,
            recs,
            "User should be able to read action when conditions are met",
        )

        # Case 2: User should not be able to read when access_level > "1"
        self.test_plan.access_level = "2"
        recs = self.plan_line_action.with_user(self.user).search(
            [("id", "=", self.test_action.id)]
        )
        self.assertNotIn(
            self.test_action,
            recs,
            "User should not be able to read action when access_level > '1'",
        )

        # Case 3: User should not be able to read when not in user_ids
        self.test_plan.access_level = "1"
        self.test_plan.user_ids = [(5, 0, 0)]  # Remove all users
        recs = self.plan_line_action.with_user(self.user).search(
            [("id", "=", self.test_action.id)]
        )
        self.assertNotIn(
            self.test_action,
            recs,
            "User should not be able to read action when not in user_ids",
        )

        # Case 4: User should be able to read when in server's user_ids
        self.test_plan.server_ids = [(6, 0, [self.server.id])]
        recs = self.plan_line_action.with_user(self.user).search(
            [("id", "=", self.test_action.id)]
        )
        self.assertIn(
            self.test_action,
            recs,
            "User should be able to read action when in server's user_ids",
        )

    def test_user_write_create_unlink_access(self):
        """Test user write/create/unlink access restrictions"""
        # Users should not be able to create actions
        with self.assertRaises(AccessError):
            self.plan_line_action.with_user(self.user).create(
                {
                    "line_id": self.test_plan_line.id,
                    "condition": "==",
                    "value_char": "0",
                    "action": "n",
                }
            )

        # Users should not be able to write actions
        with self.assertRaises(AccessError):
            self.test_action.with_user(self.user).write({"value_char": "1"})

        # Users should not be able to unlink actions
        with self.assertRaises(AccessError):
            self.test_action.with_user(self.user).unlink()

    def test_manager_read_access(self):
        """Test manager read access to plan line actions"""
        # Case 1: Manager should be able to read when:
        # - access_level <= "2"
        # - manager is in plan's manager_ids
        recs = self.plan_line_action.with_user(self.manager).search(
            [("id", "=", self.test_action.id)]
        )
        self.assertIn(
            self.test_action,
            recs,
            "Manager should be able to read action when conditions are met",
        )

        # Case 2: Manager should not be able to read when access_level > "2"
        self.test_plan.access_level = "3"
        recs = self.plan_line_action.with_user(self.manager).search(
            [("id", "=", self.test_action.id)]
        )
        self.assertNotIn(
            self.test_action,
            recs,
            "Manager should not be able to read action when access_level > '2'",
        )

        # Case 3: Manager should be able to read when in server's manager_ids
        self.test_plan.access_level = "2"
        self.test_plan.manager_ids = [(5, 0, 0)]  # Remove all managers
        self.test_plan.server_ids = [(6, 0, [self.server.id])]
        recs = self.plan_line_action.with_user(self.manager).search(
            [("id", "=", self.test_action.id)]
        )
        self.assertIn(
            self.test_action,
            recs,
            "Manager should be able to read when in server's manager_ids",
        )

    def test_manager_write_create_access(self):
        """Test manager write/create access to plan line actions"""
        # Case 1: Manager should be able to create/write when:
        # - access_level <= "2"
        # - manager is in plan's manager_ids
        try:
            # Test create
            self.plan_line_action.with_user(self.manager).create(
                {
                    "line_id": self.test_plan_line.id,
                    "condition": "==",
                    "value_char": "1",
                    "action": "n",
                }
            )
            # Test write
            self.test_action.with_user(self.manager).write({"value_char": "2"})
        except AccessError:
            self.fail("Manager should be able to create/write when conditions are met")

        # Case 2: Manager should not be able to create/write when access_level > "2"
        self.test_plan.access_level = "3"
        with self.assertRaises(AccessError):
            self.plan_line_action.with_user(self.manager).create(
                {
                    "line_id": self.test_plan_line.id,
                    "condition": "==",
                    "value_char": "1",
                    "action": "n",
                }
            )
        with self.assertRaises(AccessError):
            self.test_action.with_user(self.manager).write({"value_char": "3"})

    def test_manager_unlink_access(self):
        """Test manager unlink access to plan line actions"""
        # Create action as manager to test unlink rights
        action = self.plan_line_action.with_user(self.manager).create(
            {
                "line_id": self.test_plan_line.id,
                "condition": "==",
                "value_char": "0",
                "action": "n",
            }
        )

        # Case 1: Manager should be able to unlink when:
        # - access_level <= "2"
        # - manager is the creator
        # - manager is in plan's manager_ids
        try:
            action.unlink()
        except AccessError:
            self.fail("Manager should be able to unlink when conditions are met")

        # Case 2: Manager should not be able to unlink actions created by others
        action = self.test_action  # Created by admin in setUp
        with self.assertRaises(AccessError):
            action.with_user(self.manager).unlink()

    def test_root_unrestricted_access(self):
        """Test root user unrestricted access"""
        # Root should have full access regardless of conditions
        try:
            # Test read
            recs = self.plan_line_action.with_user(self.root).search(
                [("id", "=", self.test_action.id)]
            )
            self.assertIn(
                self.test_action,
                recs,
                "Root should be able to read action without restrictions",
            )

            # Test create
            new_action = self.plan_line_action.with_user(self.root).create(
                {
                    "line_id": self.test_plan_line.id,
                    "condition": "==",
                    "value_char": "1",
                    "action": "n",
                }
            )

            # Test write
            self.test_action.with_user(self.root).write({"value_char": "2"})

            # Test unlink
            new_action.unlink()
        except AccessError:
            self.fail("Root user should have unrestricted access")
