# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError

from .common_jets import TestTowerJetsCommon


class TestTowerJetWaypointTemplateAccess(TestTowerJetsCommon):
    """
    Test access rules for Jet Waypoint Template model
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Use existing users from common.py (cls.user, cls.manager, cls.root)
        # Create additional manager for multi-manager tests
        cls.manager2 = cls.Users.create(
            {
                "name": "Test Manager 2",
                "login": "test_manager_2",
                "email": "test_manager_2@example.com",
                "groups_id": [(6, 0, [cls.group_manager.id])],
            }
        )

    # ======================
    # Manager Read Access Tests
    # ======================

    def test_manager_read_access_user_ids(self):
        """Test Manager: Read when user is added in template's user_ids"""
        # Create jet template with manager in user_ids
        jet_template = self.JetTemplate.create(
            {
                "name": "Test Template",
                "reference": "test_template",
                "user_ids": [(4, self.manager.id)],
            }
        )

        record = self.JetWaypointTemplate.create(
            {
                "name": "Waypoint with User Access",
                "reference": "waypoint_user_access",
                "jet_template_id": jet_template.id,
                "access_level": "2",  # Manager level
            }
        )

        records = self.JetWaypointTemplate.with_user(self.manager).search(
            [("id", "=", record.id)]
        )
        self.assertEqual(
            len(records),
            1,
            "Manager should be able to read when added to template's user_ids",
        )

    def test_manager_read_access_manager_ids(self):
        """Test Manager: Read when user is added in template's manager_ids"""
        # Create jet template with manager in manager_ids
        jet_template = self.JetTemplate.create(
            {
                "name": "Test Template",
                "reference": "test_template",
                "manager_ids": [(4, self.manager.id)],
            }
        )

        record = self.JetWaypointTemplate.create(
            {
                "name": "Waypoint with Manager Access",
                "reference": "waypoint_manager_access",
                "jet_template_id": jet_template.id,
                "access_level": "2",  # Manager level
            }
        )

        records = self.JetWaypointTemplate.with_user(self.manager).search(
            [("id", "=", record.id)]
        )
        self.assertEqual(
            len(records),
            1,
            "Manager should be able to read when added to template's manager_ids",
        )

    def test_manager_read_no_access_root_level(self):
        """
        Test Manager: No read access for Root level (3)
        without user_ids/manager_ids
        """
        # Create jet template without manager access
        jet_template = self.JetTemplate.create(
            {
                "name": "Test Template",
                "reference": "test_template",
                "user_ids": False,
                "manager_ids": False,
            }
        )

        record = self.JetWaypointTemplate.create(
            {
                "name": "Root Level Waypoint",
                "reference": "root_level_waypoint",
                "jet_template_id": jet_template.id,
                "access_level": "3",  # Root level
            }
        )

        records = self.JetWaypointTemplate.with_user(self.manager).search(
            [("id", "=", record.id)]
        )
        self.assertEqual(
            len(records),
            0,
            "Manager should not read access_level='3' "
            "when not in template's user_ids or manager_ids",
        )

    def test_manager_read_no_access_not_in_template(self):
        """Test Manager: No read access when not in template's Users or Managers"""
        # Create jet template without manager access
        jet_template = self.JetTemplate.create(
            {
                "name": "Test Template",
                "reference": "test_template",
                "user_ids": False,
                "manager_ids": False,
            }
        )

        record = self.JetWaypointTemplate.create(
            {
                "name": "No Access Waypoint",
                "reference": "no_access_waypoint",
                "jet_template_id": jet_template.id,
                "access_level": "2",  # Manager level
            }
        )

        records = self.JetWaypointTemplate.with_user(self.manager).search(
            [("id", "=", record.id)]
        )
        self.assertEqual(
            len(records),
            0,
            "Manager should not read when not in template's user_ids or manager_ids",
        )

    # ======================
    # Manager Write/Create Access Tests
    # ======================

    def test_manager_write_access_level_and_manager_ids(self):
        """Test Manager: Write when access_level <= 2 AND in template's manager_ids"""
        # Create jet template with manager in manager_ids
        jet_template = self.JetTemplate.create(
            {
                "name": "Test Template",
                "reference": "test_template",
                "manager_ids": [(4, self.manager.id)],
            }
        )

        record = self.JetWaypointTemplate.create(
            {
                "name": "Manager Can Write",
                "reference": "manager_can_write",
                "jet_template_id": jet_template.id,
                "access_level": "2",
            }
        )

        # Manager should be able to write
        try:
            record.with_user(self.manager).write({"name": "Updated Name"})
            record.invalidate_recordset()
            self.assertEqual(
                record.name, "Updated Name", "Manager should be able to update"
            )
        except AccessError:
            self.fail("Manager should be able to update when in template's manager_ids")

    def test_manager_write_forbidden_not_in_manager_ids(self):
        """Test Manager: No write when not in template's manager_ids"""
        # Create jet template with manager only in user_ids, not manager_ids
        jet_template = self.JetTemplate.create(
            {
                "name": "Test Template",
                "reference": "test_template",
                "user_ids": [(4, self.manager.id)],  # Only in user_ids
                "manager_ids": False,
            }
        )

        record = self.JetWaypointTemplate.create(
            {
                "name": "No Write Access",
                "reference": "no_write_access",
                "jet_template_id": jet_template.id,
                "access_level": "2",
            }
        )

        with self.assertRaises(AccessError):
            record.with_user(self.manager).write({"name": "Should Fail"})

    def test_manager_write_forbidden_root_level(self):
        """Test Manager: No write when access_level is Root (3)"""
        # Create jet template with manager in manager_ids
        jet_template = self.JetTemplate.create(
            {
                "name": "Test Template",
                "reference": "test_template",
                "manager_ids": [(4, self.manager.id)],
            }
        )

        record = self.JetWaypointTemplate.create(
            {
                "name": "Root Level No Write",
                "reference": "root_level_no_write",
                "jet_template_id": jet_template.id,
                "access_level": "3",  # Root level
            }
        )

        with self.assertRaises(AccessError):
            record.with_user(self.manager).write({"name": "Should Fail"})

    def test_manager_create_access(self):
        """Test Manager: Create when access_level <= 2 AND in template's manager_ids"""
        # Create jet template with manager in manager_ids
        jet_template = self.JetTemplate.create(
            {
                "name": "Test Template",
                "reference": "test_template",
                "manager_ids": [(4, self.manager.id)],
            }
        )

        # Try to create without being in manager_ids - should fail
        jet_template_no_access = self.JetTemplate.create(
            {
                "name": "No Access Template",
                "reference": "no_access_template",
                "manager_ids": False,
            }
        )

        with self.assertRaises(AccessError):
            self.JetWaypointTemplate.with_user(self.manager).create(
                {
                    "name": "Create Fail",
                    "reference": "create_fail",
                    "jet_template_id": jet_template_no_access.id,
                    "access_level": "2",
                }
            )

        # Create with manager in template's manager_ids - should succeed
        try:
            record = self.JetWaypointTemplate.with_user(self.manager).create(
                {
                    "name": "Create Success",
                    "reference": "create_success",
                    "jet_template_id": jet_template.id,
                    "access_level": "2",
                }
            )
            records = self.JetWaypointTemplate.search([("id", "=", record.id)])
            self.assertEqual(len(records), 1, "Manager should be able to create")
        except AccessError:
            self.fail("Manager should be able to create when in template's manager_ids")

    # ======================
    # Manager Delete Access Tests
    # ======================

    def test_manager_delete_own_record(self):
        """Test Manager: Delete own record when in template's manager_ids"""
        # Create jet template with manager in manager_ids
        jet_template = self.JetTemplate.create(
            {
                "name": "Test Template",
                "reference": "test_template",
                "manager_ids": [(4, self.manager.id)],
            }
        )

        record = self.JetWaypointTemplate.with_user(self.manager).create(
            {
                "name": "My Record",
                "reference": "my_record",
                "jet_template_id": jet_template.id,
                "access_level": "2",
            }
        )

        try:
            record.with_user(self.manager).unlink()
            records = self.JetWaypointTemplate.search([("id", "=", record.id)])
            self.assertEqual(
                len(records), 0, "Manager should be able to delete own record"
            )
        except AccessError:
            self.fail("Manager should be able to delete own record")

    def test_manager_delete_not_creator(self):
        """Test Manager: Cannot delete record created by another user"""
        # Create jet template with both managers in manager_ids
        jet_template = self.JetTemplate.create(
            {
                "name": "Test Template",
                "reference": "test_template",
                "manager_ids": [(4, self.manager.id), (4, self.manager2.id)],
            }
        )

        record = self.JetWaypointTemplate.with_user(self.manager2).create(
            {
                "name": "Other's Record",
                "reference": "others_record",
                "jet_template_id": jet_template.id,
                "access_level": "2",
            }
        )

        # Manager1 cannot delete Manager2's record
        with self.assertRaises(AccessError):
            record.with_user(self.manager).unlink()

    def test_manager_delete_not_in_manager_ids(self):
        """Test Manager: Cannot delete when not in template's manager_ids"""
        # Create jet template with manager in manager_ids
        jet_template = self.JetTemplate.create(
            {
                "name": "Test Template",
                "reference": "test_template",
                "manager_ids": [(4, self.manager.id)],
            }
        )

        record = self.JetWaypointTemplate.with_user(self.manager).create(
            {
                "name": "Removed Manager",
                "reference": "removed_manager",
                "jet_template_id": jet_template.id,
                "access_level": "2",
            }
        )

        # Remove from manager_ids
        jet_template.write({"manager_ids": False})

        # Cannot delete anymore
        with self.assertRaises(AccessError):
            record.with_user(self.manager).unlink()

    def test_manager_delete_root_level(self):
        """Test Manager: Cannot delete Root level record"""
        # Create jet template with manager in manager_ids
        jet_template = self.JetTemplate.create(
            {
                "name": "Test Template",
                "reference": "test_template",
                "manager_ids": [(4, self.manager.id)],
            }
        )

        # Create record with Root level as root (default user)
        record = self.JetWaypointTemplate.create(
            {
                "name": "Root Level Delete",
                "reference": "root_level_delete",
                "jet_template_id": jet_template.id,
                "access_level": "3",  # Root level
            }
        )

        with self.assertRaises(AccessError):
            record.with_user(self.manager).unlink()

    # ======================
    # Root Access Tests
    # ======================

    def test_root_full_access(self):
        """
        Test Root: Full CRUD access regardless of access_level or creator.

        Root has unrestricted access to all records via security rule
        [(1, '=', 1)], so we test:
        - Create records with all access levels
        - Read records with all access levels
        - Write to records with all access levels
        - Delete records regardless of creator
        """
        # Create jet template for testing
        jet_template = self.JetTemplate.create(
            {
                "name": "Test Template",
                "reference": "test_template",
            }
        )

        # Test CRUD operations for all access levels (only Manager and Root exist)
        for access_level in ["2", "3"]:
            # Root can create any level
            record = self.JetWaypointTemplate.with_user(self.root).create(
                {
                    "name": f"Root Level {access_level}",
                    "reference": f"root_level_{access_level}",
                    "jet_template_id": jet_template.id,
                    "access_level": access_level,
                }
            )

            # Root can read any level
            records = self.JetWaypointTemplate.with_user(self.root).search(
                [("id", "=", record.id)]
            )
            self.assertEqual(
                len(records),
                1,
                f"Root should be able to read access_level={access_level}",
            )

            # Root can write any level
            record.with_user(self.root).write(
                {"name": f"Root Updated Level {access_level}"}
            )
            record.invalidate_recordset()
            self.assertEqual(
                record.name,
                f"Root Updated Level {access_level}",
                f"Root should be able to update access_level={access_level}",
            )

        # Test Root can delete records created by other users
        # Add manager to template's manager_ids so they can create the record
        jet_template.write({"manager_ids": [(4, self.manager.id)]})
        manager_record = self.JetWaypointTemplate.with_user(self.manager).create(
            {
                "name": "Manager's Record",
                "reference": "managers_record",
                "jet_template_id": jet_template.id,
                "access_level": "2",
            }
        )
        manager_record.with_user(self.root).unlink()
        records = self.JetWaypointTemplate.with_user(self.root).search(
            [("id", "=", manager_record.id)]
        )
        self.assertEqual(
            len(records),
            0,
            "Root should be able to delete records from any creator",
        )

    # ======================
    # Edge Cases
    # ======================

    def test_access_level_changes_visibility(self):
        """Test that changing access_level affects visibility"""
        # Create jet template with manager in manager_ids
        jet_template = self.JetTemplate.create(
            {
                "name": "Test Template",
                "reference": "test_template",
                "manager_ids": [(4, self.manager.id)],
            }
        )

        # Create with Manager level
        record = self.JetWaypointTemplate.create(
            {
                "name": "Changing Level",
                "reference": "changing_level",
                "jet_template_id": jet_template.id,
                "access_level": "2",
            }
        )

        # Manager can read
        records = self.JetWaypointTemplate.with_user(self.manager).search(
            [("id", "=", record.id)]
        )
        self.assertEqual(len(records), 1, "Manager should read level 2")

        # Change to Root level
        record.write({"access_level": "3"})

        # Manager cannot read anymore
        records = self.JetWaypointTemplate.with_user(self.manager).search(
            [("id", "=", record.id)]
        )
        self.assertEqual(len(records), 0, "Manager should not read level 3")
