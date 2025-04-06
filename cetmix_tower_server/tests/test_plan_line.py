# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError

from .common import TestTowerCommon


class TestTowerPlanLine(TestTowerCommon):
    """Test the cx.tower.plan.line model access rights."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

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
        cls.test_line = cls.plan_line.create(
            {
                "plan_id": cls.test_plan.id,
                "command_id": cls.command_create_dir.id,
                "sequence": 10,
            }
        )

        # Create additional servers for testing server-based access
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

        cls.server_3 = cls.Server.create(
            {
                "name": "Test Server 3",
                "ip_v4_address": "localhost",
                "ssh_username": "test3",
                "ssh_password": "test3",
                "ssh_port": 22,
                "user_ids": [(6, 0, [])],
                "manager_ids": [(6, 0, [])],
            }
        )

    def test_user_read_access(self):
        """Test user read access to plan lines"""
        # Case 1: User should be able to read line when:
        # - access_level == "1"
        # - user is in plan's user_ids OR server's user_ids
        recs = self.plan_line.with_user(self.user).search(
            [("id", "=", self.test_line.id)]
        )
        self.assertIn(
            self.test_line,
            recs,
            "User should be able to read line when conditions are met",
        )

        # Case 2: User should not be able to read when access_level > "1"
        self.test_plan.write(
            {
                "access_level": "2",
            }
        )
        recs = self.plan_line.with_user(self.user).search(
            [("id", "=", self.test_line.id)]
        )
        self.assertNotIn(
            self.test_line,
            recs,
            "User should not be able to read line when access_level > '1'",
        )

        # Case 3: User should be able to read when in server's user_ids
        self.test_plan.write(
            {
                "access_level": "1",
                "server_ids": [(6, 0, [self.server_test_1.id])],
            }
        )
        self.server_test_1.write(
            {
                "user_ids": [(6, 0, [self.user.id])],
            }
        )
        recs = self.plan_line.with_user(self.user).search(
            [("id", "=", self.test_line.id)]
        )
        self.assertIn(
            self.test_line,
            recs,
            "User should be able to read line when in server's user_ids",
        )

    def test_user_write_create_unlink_access(self):
        """Test user write/create/unlink access restrictions"""
        # Users should not be able to create lines
        with self.assertRaises(AccessError):
            self.plan_line.with_user(self.user).create(
                {
                    "plan_id": self.test_plan.id,
                    "command_id": self.command_create_dir.id,
                    "sequence": 20,
                }
            )

        # Users should not be able to write lines
        with self.assertRaises(AccessError):
            self.test_line.with_user(self.user).write({"sequence": 30})

        # Users should not be able to unlink lines
        with self.assertRaises(AccessError):
            self.test_line.with_user(self.user).unlink()

    def test_manager_read_access(self):
        """Test manager read access to plan lines"""
        # Case 1: Manager should be able to read when:
        # - access_level <= "2"
        # - manager is in plan's manager_ids OR user_ids
        recs = self.plan_line.with_user(self.manager).search(
            [("id", "=", self.test_line.id)]
        )
        self.assertIn(
            self.test_line,
            recs,
            "Manager should be able to read line when conditions are met",
        )

        # Case 2: Manager should not be able to read when access_level > "2"
        self.test_plan.write(
            {
                "access_level": "3",
                "manager_ids": [(5, 0, 0)],  # Remove all managers
            }
        )
        recs = self.plan_line.with_user(self.manager).search(
            [("id", "=", self.test_line.id)]
        )
        self.assertNotIn(
            self.test_line,
            recs,
            "Manager should not be able to read line when access_level > '2'",
        )

        # Case 2.5: Manager not not be able to read when not in plan managers
        self.test_plan.write(
            {
                "access_level": "2",
                "manager_ids": [(5, 0, 0)],  # Remove all managers
                "server_ids": [(6, 0, [self.server_test_1.id])],
            }
        )
        self.server_test_1.write(
            {
                "user_ids": [(5, 0, 0)],  # Remove all users
                "manager_ids": [(5, 0, 0)],  # Remove all managers
            }
        )
        recs = self.plan_line.with_user(self.manager).search(
            [("id", "=", self.test_line.id)]
        )
        self.assertNotIn(
            self.test_line,
            recs,
            "Manager should not be able to read line when access_level > '2'",
        )

        # Case 3: Manager should be able to read when in server's manager_ids
        self.test_plan.write(
            {
                "access_level": "2",
                "server_ids": [(6, 0, [self.server_test_1.id])],
            }
        )
        self.server_test_1.write(
            {
                "manager_ids": [(6, 0, [self.manager.id])],
            }
        )
        recs = self.plan_line.with_user(self.manager).search(
            [("id", "=", self.test_line.id)]
        )
        self.assertIn(
            self.test_line,
            recs,
            "Manager should be able to read line when in server's manager_ids",
        )

    def test_manager_write_create_access(self):
        """Test manager write/create access to plan lines"""
        # Case 1: Manager should be able to create/write when:
        # - access_level <= "2"
        # - manager is in plan's manager_ids
        try:
            # Test create
            self.plan_line.with_user(self.manager).create(
                {
                    "plan_id": self.test_plan.id,
                    "command_id": self.command_create_dir.id,
                    "sequence": 20,
                }
            )
            # Test write
            self.test_line.with_user(self.manager).write({"sequence": 30})
        except AccessError:
            self.fail("Manager should be able to create/write when conditions are met")

        # Case 2: Manager should not be able to create/write when access_level > "2"
        self.test_plan.write(
            {
                "access_level": "3",
            }
        )
        with self.assertRaises(AccessError):
            self.plan_line.with_user(self.manager).create(
                {
                    "plan_id": self.test_plan.id,
                    "command_id": self.command_create_dir.id,
                    "sequence": 40,
                }
            )
        with self.assertRaises(AccessError):
            self.test_line.with_user(self.manager).write({"sequence": 50})

    def test_manager_unlink_access(self):
        """Test manager unlink access to plan lines"""
        # Create line as manager to test unlink rights
        line = self.plan_line.with_user(self.manager).create(
            {
                "plan_id": self.test_plan.id,
                "command_id": self.command_create_dir.id,
                "sequence": 20,
            }
        )

        # Case 1: Manager should be able to unlink when:
        # - access_level <= "2"
        # - manager is the creator
        # - manager is in plan's manager_ids
        try:
            line.unlink()
        except AccessError:
            self.fail("Manager should be able to unlink when conditions are met")

        # Case 2: Manager should not be able to unlink lines created by others
        line = self.test_line  # Created by admin in setUp
        with self.assertRaises(AccessError):
            line.with_user(self.manager).unlink()

    def test_root_unrestricted_read_access(self):
        """Test root user unrestricted read access"""
        # Set most restrictive conditions
        self.test_plan.write(
            {
                "access_level": "3",
                "user_ids": [(5, 0, 0)],
                "manager_ids": [(5, 0, 0)],
                "server_ids": [(6, 0, [self.server_2.id, self.server_3.id])],
            }
        )

        # Root should still be able to read
        recs = self.plan_line.with_user(self.root).search(
            [("id", "=", self.test_line.id)]
        )
        self.assertIn(
            self.test_line,
            recs,
            "Root should be able to read regardless of access restrictions",
        )

        # Root should be able to read all records
        all_recs = self.plan_line.with_user(self.root).search([])
        self.assertIn(
            self.test_line,
            all_recs,
            "Root should be able to read all records",
        )

    def test_root_unrestricted_write_access(self):
        """Test root user unrestricted write access"""
        # Set most restrictive conditions
        self.test_plan.write(
            {
                "access_level": "3",
                "user_ids": [(5, 0, 0)],
                "manager_ids": [(5, 0, 0)],
                "server_ids": [(6, 0, [self.server_2.id, self.server_3.id])],
            }
        )

        try:
            # Test single field update
            self.test_line.with_user(self.root).write({"sequence": 100})

            # Test multiple field update
            self.test_line.with_user(self.root).write(
                {
                    "sequence": 200,
                    "path": "/test/path",
                    "use_sudo": True,
                }
            )
        except AccessError:
            self.fail("Root should be able to write regardless of access restrictions")

    def test_root_unrestricted_create_access(self):
        """Test root user unrestricted create access"""
        # Set most restrictive conditions
        self.test_plan.write(
            {
                "access_level": "3",
                "user_ids": [(5, 0, 0)],
                "manager_ids": [(5, 0, 0)],
                "server_ids": [(6, 0, [self.server_2.id, self.server_3.id])],
            }
        )

        try:
            # Test create with minimal values
            new_line_1 = self.plan_line.with_user(self.root).create(
                {
                    "plan_id": self.test_plan.id,
                    "command_id": self.command_create_dir.id,
                }
            )

            # Test create with all values
            new_line_2 = self.plan_line.with_user(self.root).create(
                {
                    "plan_id": self.test_plan.id,
                    "command_id": self.command_create_dir.id,
                    "sequence": 300,
                    "path": "/another/test/path",
                    "use_sudo": True,
                    "condition": "{{ test_condition }}",
                }
            )

            # Verify created records are readable
            recs = self.plan_line.with_user(self.root).search(
                [("id", "in", [new_line_1.id, new_line_2.id])]
            )
            self.assertEqual(
                len(recs),
                2,
                "Root should be able to read newly created records",
            )
        except AccessError:
            self.fail("Root should be able to create regardless of access restrictions")

    def test_root_unrestricted_unlink_access(self):
        """Test root user unrestricted unlink access"""
        # Set most restrictive conditions
        self.test_plan.write(
            {
                "access_level": "3",
                "user_ids": [(5, 0, 0)],
                "manager_ids": [(5, 0, 0)],
                "server_ids": [(6, 0, [self.server_2.id, self.server_3.id])],
            }
        )

        # Create test records
        test_lines = self.plan_line.with_user(self.root).create(
            [
                {
                    "plan_id": self.test_plan.id,
                    "command_id": self.command_create_dir.id,
                    "sequence": seq,
                }
                for seq in range(400, 403)
            ]
        )

        try:
            # Test single record unlink
            test_lines[0].with_user(self.root).unlink()

            # Test multiple record unlink
            test_lines[1:].with_user(self.root).unlink()

            # Verify records are deleted
            recs = self.plan_line.with_user(self.root).search(
                [("id", "in", test_lines.ids)]
            )
            self.assertEqual(
                len(recs),
                0,
                "Root should be able to delete records completely",
            )
        except AccessError:
            self.fail("Root should be able to unlink regardless of access restrictions")

    def test_manager_server_based_read_access(self):
        """Test manager read access based on server relationships"""
        # Remove direct manager access from plan
        self.test_plan.write(
            {
                "manager_ids": [(5, 0, 0)],  # Clear manager_ids
                "access_level": "2",
            }
        )

        # Case 1: No servers linked - should have access
        recs = self.plan_line.with_user(self.manager).search(
            [("id", "=", self.test_line.id)]
        )
        self.assertIn(
            self.test_line,
            recs,
            "Manager should be able to read when no servers are linked",
        )

        # Case 2: Server linked but manager not in server's users/managers
        self.test_plan.write(
            {
                "server_ids": [(6, 0, [self.server_2.id])],
            }
        )
        recs = self.plan_line.with_user(self.manager).search(
            [("id", "=", self.test_line.id)]
        )
        self.assertNotIn(
            self.test_line,
            recs,
            "Manager should not be able to read when not in server's users/managers",
        )

        # Case 3: Manager in server's user_ids
        self.server_2.write(
            {
                "user_ids": [(6, 0, [self.manager.id])],
            }
        )
        recs = self.plan_line.with_user(self.manager).search(
            [("id", "=", self.test_line.id)]
        )
        self.assertIn(
            self.test_line,
            recs,
            "Manager should be able to read when in server's user_ids",
        )

        # Case 4: Manager in server's manager_ids
        self.server_2.write(
            {
                "user_ids": [(5, 0, 0)],
                "manager_ids": [(6, 0, [self.manager.id])],
            }
        )
        recs = self.plan_line.with_user(self.manager).search(
            [("id", "=", self.test_line.id)]
        )
        self.assertIn(
            self.test_line,
            recs,
            "Manager should be able to read when in server's manager_ids",
        )

        # Case 5: Multiple servers - access through one server
        self.test_plan.write(
            {
                "server_ids": [(6, 0, [self.server_2.id, self.server_3.id])],
            }
        )
        recs = self.plan_line.with_user(self.manager).search(
            [("id", "=", self.test_line.id)]
        )
        self.assertIn(
            self.test_line,
            recs,
            "Manager should be able to read when in at least one server's manager_ids",
        )

        # Case 6: Multiple servers - no access
        self.server_2.write(
            {
                "manager_ids": [(5, 0, 0)],
            }
        )
        recs = self.plan_line.with_user(self.manager).search(
            [("id", "=", self.test_line.id)]
        )
        self.assertNotIn(
            self.test_line,
            recs,
            "Manager should not be able to read when not "
            "in any server's users/managers",
        )

    def test_manager_server_based_write_access(self):
        """Test manager write access based on server relationships"""
        # Remove direct manager access from plan
        self.test_plan.write(
            {
                "manager_ids": [(5, 0, 0)],  # Clear manager_ids
                "access_level": "2",
                "server_ids": [(6, 0, [self.server_2.id])],
            }
        )

        # Case 1: No server access - should not be able to write
        with self.assertRaises(AccessError):
            self.test_line.with_user(self.manager).write({"sequence": 40})

        # Case 2: Manager in server's manager_ids - still should not be able to write
        self.server_2.write(
            {
                "manager_ids": [(6, 0, [self.manager.id])],
            }
        )
        with self.assertRaises(AccessError):
            self.test_line.with_user(self.manager).write({"sequence": 50})

        # Case 3: Manager in plan's manager_ids - should be able to write
        self.test_plan.write(
            {
                "manager_ids": [(6, 0, [self.manager.id])],
            }
        )
        try:
            self.test_line.with_user(self.manager).write({"sequence": 60})
        except AccessError:
            self.fail("Manager should be able to write when in plan's manager_ids")
