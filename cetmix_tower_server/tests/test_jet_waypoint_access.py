# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError

from .common_jets import TestTowerJetsCommon


class TestTowerJetWaypointAccess(TestTowerJetsCommon):
    """
    Test access rules for Jet Waypoint model
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

    def test_manager_read_access_jet_user_ids(self):
        """Test Manager: Read when user is added in jet's user_ids"""
        # Use existing jet and add manager to user_ids
        self.jet_test.write({"user_ids": [(4, self.manager.id)]})
        jet = self.jet_test

        record = self.JetWaypoint.create(
            {
                "name": "Waypoint with User Access",
                "reference": "waypoint_user_access",
                "jet_id": jet.id,
                "waypoint_template_id": self.waypoint_template.id,
            }
        )

        records = self.JetWaypoint.with_user(self.manager).search(
            [("id", "=", record.id)]
        )
        self.assertEqual(
            len(records),
            1,
            "Manager should be able to read when added to jet's user_ids",
        )

    def test_manager_read_access_jet_manager_ids(self):
        """Test Manager: Read when user is added in jet's manager_ids"""
        # Use existing jet and add manager to manager_ids
        self.jet_test.write({"manager_ids": [(4, self.manager.id)]})
        jet = self.jet_test

        record = self.JetWaypoint.create(
            {
                "name": "Waypoint with Manager Access",
                "reference": "waypoint_manager_access",
                "jet_id": jet.id,
                "waypoint_template_id": self.waypoint_template.id,
            }
        )

        records = self.JetWaypoint.with_user(self.manager).search(
            [("id", "=", record.id)]
        )
        self.assertEqual(
            len(records),
            1,
            "Manager should be able to read when added to jet's manager_ids",
        )

    def test_manager_read_no_access_root_level(self):
        """Test Manager: No read access for Root level (3) even with jet access"""
        # Use existing jet and add manager to manager_ids (has jet access)
        self.jet_test.write({"manager_ids": [(4, self.manager.id)]})
        jet = self.jet_test

        # Create waypoint template with Root level
        waypoint_template_root = self.JetWaypointTemplate.create(
            {
                "name": "Root Level Template",
                "reference": "root_level_template",
                "jet_template_id": self.jet_template_test.id,
                "access_level": "3",  # Root level
            }
        )

        record = self.JetWaypoint.create(
            {
                "name": "Root Level Waypoint",
                "reference": "root_level_waypoint",
                "jet_id": jet.id,
                "waypoint_template_id": waypoint_template_root.id,
                "access_level": "3",  # Explicitly set Root level
            }
        )

        records = self.JetWaypoint.with_user(self.manager).search(
            [("id", "=", record.id)]
        )
        self.assertEqual(
            len(records),
            0,
            "Manager should not read access_level='3' "
            "even when in jet's manager_ids (Root level blocks access)",
        )

    def test_manager_read_no_access_not_in_jet(self):
        """Test Manager: No read access when not in jet's Users or Managers"""
        # Use existing jet (manager not in user_ids/manager_ids)
        jet = self.jet_test

        record = self.JetWaypoint.create(
            {
                "name": "No Access Waypoint",
                "reference": "no_access_waypoint",
                "jet_id": jet.id,
                "waypoint_template_id": self.waypoint_template.id,
            }
        )

        records = self.JetWaypoint.with_user(self.manager).search(
            [("id", "=", record.id)]
        )
        self.assertEqual(
            len(records),
            0,
            "Manager should not read when not in jet's user_ids or manager_ids",
        )

    # ======================
    # Manager Write/Create Access Tests
    # ======================

    def test_manager_write_access_level_and_template_manager_ids(self):
        """Test Manager: Write when access_level <= 2 AND in template's manager_ids"""
        # Create jet template with manager in manager_ids
        jet_template = self.JetTemplate.create(
            {
                "name": "Test Template",
                "reference": "test_template",
                "manager_ids": [(4, self.manager.id)],
            }
        )

        # Create jet from this template with unique name
        jet = self._create_jet(
            name="Write Access Jet",
            reference="write_access_jet",
            template=jet_template,
            server=self.server_test_1,
        )

        # Create waypoint template
        waypoint_template = self.JetWaypointTemplate.create(
            {
                "name": "Test Waypoint Template",
                "reference": "test_waypoint_template",
                "jet_template_id": jet_template.id,
            }
        )

        record = self.JetWaypoint.create(
            {
                "name": "Manager Can Write",
                "reference": "manager_can_write",
                "jet_id": jet.id,
                "waypoint_template_id": waypoint_template.id,
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

    def test_manager_write_forbidden_not_in_template_manager_ids(self):
        """Test Manager: No write when not in template's manager_ids"""
        # Create jet template without manager in manager_ids
        jet_template = self.JetTemplate.create(
            {
                "name": "Test Template",
                "reference": "test_template",
                "manager_ids": False,
            }
        )

        # Create jet with manager in manager_ids (for read access)
        jet = self._create_jet(
            name="No Write Jet",
            reference="no_write_jet",
            template=jet_template,
            server=self.server_test_1,
            manager_ids=[(4, self.manager.id)],
        )

        # Create waypoint template
        waypoint_template = self.JetWaypointTemplate.create(
            {
                "name": "Test Waypoint Template",
                "reference": "test_waypoint_template",
                "jet_template_id": jet_template.id,
            }
        )

        record = self.JetWaypoint.create(
            {
                "name": "No Write Access",
                "reference": "no_write_access",
                "jet_id": jet.id,
                "waypoint_template_id": waypoint_template.id,
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

        # Create jet from this template with unique name
        jet = self._create_jet(
            name="Write Access Jet",
            reference="write_access_jet",
            template=jet_template,
            server=self.server_test_1,
        )

        # Create waypoint template with Root level
        waypoint_template_root = self.JetWaypointTemplate.create(
            {
                "name": "Root Level Template",
                "reference": "root_level_template",
                "jet_template_id": jet_template.id,
                "access_level": "3",  # Root level
            }
        )

        record = self.JetWaypoint.create(
            {
                "name": "Root Level No Write",
                "reference": "root_level_no_write",
                "jet_id": jet.id,
                "waypoint_template_id": waypoint_template_root.id,
                "access_level": "3",  # Explicitly set Root level
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

        # Create jet from this template with unique name
        jet = self._create_jet(
            name="Write Access Jet",
            reference="write_access_jet",
            template=jet_template,
            server=self.server_test_1,
        )

        # Create waypoint template
        waypoint_template = self.JetWaypointTemplate.create(
            {
                "name": "Test Waypoint Template",
                "reference": "test_waypoint_template",
                "jet_template_id": jet_template.id,
            }
        )

        # Try to create without being in template's manager_ids - should fail
        jet_template_no_access = self.JetTemplate.create(
            {
                "name": "No Access Template",
                "reference": "no_access_template",
                "manager_ids": False,
            }
        )

        jet_no_access = self._create_jet(
            name="No Access Jet",
            reference="no_access_jet",
            template=jet_template_no_access,
            server=self.server_test_1,
            manager_ids=[(4, self.manager.id)],  # Manager in jet but not template
        )

        waypoint_template_no_access = self.JetWaypointTemplate.create(
            {
                "name": "No Access Waypoint Template",
                "reference": "no_access_waypoint_template",
                "jet_template_id": jet_template_no_access.id,
            }
        )

        with self.assertRaises(AccessError):
            self.JetWaypoint.with_user(self.manager).create(
                {
                    "name": "Create Fail",
                    "reference": "create_fail",
                    "jet_id": jet_no_access.id,
                    "waypoint_template_id": waypoint_template_no_access.id,
                }
            )

        # Create with manager in template's manager_ids - should succeed
        try:
            record = self.JetWaypoint.with_user(self.manager).create(
                {
                    "name": "Create Success",
                    "reference": "create_success",
                    "jet_id": jet.id,
                    "waypoint_template_id": waypoint_template.id,
                }
            )
            records = self.JetWaypoint.search([("id", "=", record.id)])
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

        # Create jet from this template with unique name
        jet = self._create_jet(
            name="Write Access Jet",
            reference="write_access_jet",
            template=jet_template,
            server=self.server_test_1,
        )

        # Create waypoint template
        waypoint_template = self.JetWaypointTemplate.create(
            {
                "name": "Test Waypoint Template",
                "reference": "test_waypoint_template",
                "jet_template_id": jet_template.id,
            }
        )

        record = self.JetWaypoint.with_user(self.manager).create(
            {
                "name": "My Record",
                "reference": "my_record",
                "jet_id": jet.id,
                "waypoint_template_id": waypoint_template.id,
            }
        )

        try:
            record.with_user(self.manager).unlink()
            records = self.JetWaypoint.search([("id", "=", record.id)])
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

        # Create jet from this template with unique name
        jet = self._create_jet(
            name="Write Access Jet",
            reference="write_access_jet",
            template=jet_template,
            server=self.server_test_1,
        )

        # Create waypoint template
        waypoint_template = self.JetWaypointTemplate.create(
            {
                "name": "Test Waypoint Template",
                "reference": "test_waypoint_template",
                "jet_template_id": jet_template.id,
            }
        )

        record = self.JetWaypoint.with_user(self.manager2).create(
            {
                "name": "Other's Record",
                "reference": "others_record",
                "jet_id": jet.id,
                "waypoint_template_id": waypoint_template.id,
            }
        )

        # Manager1 cannot delete Manager2's record
        with self.assertRaises(AccessError):
            record.with_user(self.manager).unlink()

    def test_manager_delete_not_in_template_manager_ids(self):
        """Test Manager: Cannot delete when not in template's manager_ids"""
        # Create jet template with manager in manager_ids
        jet_template = self.JetTemplate.create(
            {
                "name": "Test Template",
                "reference": "test_template",
                "manager_ids": [(4, self.manager.id)],
            }
        )

        # Create jet from this template with unique name
        jet = self._create_jet(
            name="Delete Not In Template Jet",
            reference="delete_not_in_template_jet",
            template=jet_template,
            server=self.server_test_1,
        )

        # Create waypoint template
        waypoint_template = self.JetWaypointTemplate.create(
            {
                "name": "Test Waypoint Template",
                "reference": "test_waypoint_template",
                "jet_template_id": jet_template.id,
            }
        )

        record = self.JetWaypoint.with_user(self.manager).create(
            {
                "name": "Removed Manager",
                "reference": "removed_manager",
                "jet_id": jet.id,
                "waypoint_template_id": waypoint_template.id,
            }
        )

        # Remove from template's manager_ids
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

        # Create jet from this template with unique name
        jet = self._create_jet(
            name="Write Access Jet",
            reference="write_access_jet",
            template=jet_template,
            server=self.server_test_1,
        )

        # Create waypoint template with Root level
        waypoint_template_root = self.JetWaypointTemplate.create(
            {
                "name": "Root Level Template",
                "reference": "root_level_template",
                "jet_template_id": jet_template.id,
                "access_level": "3",  # Root level
            }
        )

        # Create record with Root level as root (default user)
        record = self.JetWaypoint.create(
            {
                "name": "Root Level Delete",
                "reference": "root_level_delete",
                "jet_id": jet.id,
                "waypoint_template_id": waypoint_template_root.id,
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

        # Create jet from this template with unique name
        jet = self._create_jet(
            name="Write Access Jet",
            reference="write_access_jet",
            template=jet_template,
            server=self.server_test_1,
        )

        # Test CRUD operations for all access levels (only Manager and Root exist)
        for access_level in ["2", "3"]:
            # Create waypoint template with specific access level
            waypoint_template = self.JetWaypointTemplate.create(
                {
                    "name": f"Template Level {access_level}",
                    "reference": f"template_level_{access_level}",
                    "jet_template_id": jet_template.id,
                    "access_level": access_level,
                }
            )

            # Root can create any level
            record = self.JetWaypoint.with_user(self.root).create(
                {
                    "name": f"Root Level {access_level}",
                    "reference": f"root_level_{access_level}",
                    "jet_id": jet.id,
                    "waypoint_template_id": waypoint_template.id,
                }
            )

            # Root can read any level
            records = self.JetWaypoint.with_user(self.root).search(
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
        waypoint_template = self.JetWaypointTemplate.create(
            {
                "name": "Manager Template",
                "reference": "manager_template",
                "jet_template_id": jet_template.id,
            }
        )
        manager_record = self.JetWaypoint.with_user(self.manager).create(
            {
                "name": "Manager's Record",
                "reference": "managers_record",
                "jet_id": jet.id,
                "waypoint_template_id": waypoint_template.id,
            }
        )
        manager_record.with_user(self.root).unlink()
        records = self.JetWaypoint.with_user(self.root).search(
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

        # Create jet with manager in manager_ids with unique name
        jet = self._create_jet(
            name="Access Level Changes Jet",
            reference="access_level_changes_jet",
            template=jet_template,
            server=self.server_test_1,
            manager_ids=[(4, self.manager.id)],
        )

        # Create waypoint template with Manager level
        waypoint_template = self.JetWaypointTemplate.create(
            {
                "name": "Test Waypoint Template",
                "reference": "test_waypoint_template",
                "jet_template_id": jet_template.id,
                "access_level": "2",
            }
        )

        record = self.JetWaypoint.create(
            {
                "name": "Changing Level",
                "reference": "changing_level",
                "jet_id": jet.id,
                "waypoint_template_id": waypoint_template.id,
            }
        )

        # Manager can read
        records = self.JetWaypoint.with_user(self.manager).search(
            [("id", "=", record.id)]
        )
        self.assertEqual(len(records), 1, "Manager should read level 2")

        # Change template to Root level
        waypoint_template.write({"access_level": "3"})
        # Update waypoint's access_level since it's stored and doesn't auto-update
        record.write({"access_level": "3"})
        record.invalidate_recordset()

        # Manager cannot read anymore
        records = self.JetWaypoint.with_user(self.manager).search(
            [("id", "=", record.id)]
        )
        self.assertEqual(len(records), 0, "Manager should not read level 3")

    def test_manager_prepare_forbidden_no_write_access(self):
        """Test Manager: Cannot prepare waypoint without write access"""
        # Create jet template without manager in manager_ids
        jet_template = self.JetTemplate.create(
            {
                "name": "Test Template",
                "reference": "test_template",
                "manager_ids": False,
            }
        )

        # Create jet with manager in manager_ids (for read access)
        jet = self._create_jet(
            name="Prepare Forbidden Jet",
            reference="prepare_forbidden_jet",
            template=jet_template,
            server=self.server_test_1,
            manager_ids=[(4, self.manager.id)],
        )

        # Create waypoint template
        waypoint_template = self.JetWaypointTemplate.create(
            {
                "name": "Test Waypoint Template",
                "reference": "test_waypoint_template",
                "jet_template_id": jet_template.id,
            }
        )

        record = self.JetWaypoint.create(
            {
                "name": "Prepare Forbidden",
                "reference": "prepare_forbidden",
                "jet_id": jet.id,
                "waypoint_template_id": waypoint_template.id,
                "state": "draft",
            }
        )

        # Manager should not be able to prepare without write access
        with self.assertRaises(AccessError):
            record.with_user(self.manager).prepare()

    def test_manager_prepare_forbidden_root_level(self):
        """Test Manager: Cannot prepare waypoint with Root level"""
        # Create jet template with manager in manager_ids
        jet_template = self.JetTemplate.create(
            {
                "name": "Test Template",
                "reference": "test_template",
                "manager_ids": [(4, self.manager.id)],
            }
        )

        # Create jet from this template
        jet = self._create_jet(
            name="Prepare Root Level Jet",
            reference="prepare_root_level_jet",
            template=jet_template,
            server=self.server_test_1,
        )

        # Create waypoint template with Root level
        waypoint_template_root = self.JetWaypointTemplate.create(
            {
                "name": "Root Level Template",
                "reference": "root_level_template",
                "jet_template_id": jet_template.id,
                "access_level": "3",  # Root level
            }
        )

        record = self.JetWaypoint.create(
            {
                "name": "Root Level Prepare",
                "reference": "root_level_prepare",
                "jet_id": jet.id,
                "waypoint_template_id": waypoint_template_root.id,
                "access_level": "3",  # Explicitly set Root level
                "state": "draft",
            }
        )

        # Manager should not be able to prepare Root level waypoint
        with self.assertRaises(AccessError):
            record.with_user(self.manager).prepare()

    def test_manager_fly_to_forbidden_no_write_access(self):
        """Test Manager: Cannot fly_to waypoint without write access"""
        # Create jet template without manager in manager_ids
        jet_template = self.JetTemplate.create(
            {
                "name": "Test Template",
                "reference": "test_template",
                "manager_ids": False,
            }
        )

        # Create jet with manager in manager_ids (for read access)
        jet = self._create_jet(
            name="Fly To Forbidden Jet",
            reference="fly_to_forbidden_jet",
            template=jet_template,
            server=self.server_test_1,
            manager_ids=[(4, self.manager.id)],
        )

        # Create waypoint template
        waypoint_template = self.JetWaypointTemplate.create(
            {
                "name": "Test Waypoint Template",
                "reference": "test_waypoint_template",
                "jet_template_id": jet_template.id,
            }
        )

        record = self.JetWaypoint.create(
            {
                "name": "Fly To Forbidden",
                "reference": "fly_to_forbidden",
                "jet_id": jet.id,
                "waypoint_template_id": waypoint_template.id,
                "state": "ready",
            }
        )

        # Manager should not be able to fly_to without write access
        with self.assertRaises(AccessError):
            record.with_user(self.manager).fly_to()

    def test_manager_fly_to_forbidden_root_level(self):
        """Test Manager: Cannot fly_to waypoint with Root level"""
        # Create jet template with manager in manager_ids
        jet_template = self.JetTemplate.create(
            {
                "name": "Test Template",
                "reference": "test_template",
                "manager_ids": [(4, self.manager.id)],
            }
        )

        # Create jet from this template
        jet = self._create_jet(
            name="Fly To Root Level Jet",
            reference="fly_to_root_level_jet",
            template=jet_template,
            server=self.server_test_1,
        )

        # Create waypoint template with Root level
        waypoint_template_root = self.JetWaypointTemplate.create(
            {
                "name": "Root Level Template",
                "reference": "root_level_template",
                "jet_template_id": jet_template.id,
                "access_level": "3",  # Root level
            }
        )

        record = self.JetWaypoint.create(
            {
                "name": "Root Level Fly To",
                "reference": "root_level_fly_to",
                "jet_id": jet.id,
                "waypoint_template_id": waypoint_template_root.id,
                "access_level": "3",  # Explicitly set Root level
                "state": "ready",
            }
        )

        # Manager should not be able to fly_to Root level waypoint
        with self.assertRaises(AccessError):
            record.with_user(self.manager).fly_to()

    def test_manager_prepare_success_with_write_access(self):
        """Test Manager: Can prepare waypoint with write access"""
        # Create jet template with manager in manager_ids
        jet_template = self.JetTemplate.create(
            {
                "name": "Test Template",
                "reference": "test_template",
                "manager_ids": [(4, self.manager.id)],
            }
        )

        # Ensure manager has server access
        self.server_test_1.write({"user_ids": [(4, self.manager.id)]})

        # Create jet from this template with manager in manager_ids
        jet = self._create_jet(
            name="Prepare Success Jet",
            reference="prepare_success_jet",
            template=jet_template,
            server=self.server_test_1,
            manager_ids=[(4, self.manager.id)],
        )

        # Create waypoint template
        waypoint_template = self.JetWaypointTemplate.create(
            {
                "name": "Test Waypoint Template",
                "reference": "test_waypoint_template",
                "jet_template_id": jet_template.id,
            }
        )

        record = self.JetWaypoint.create(
            {
                "name": "Prepare Success",
                "reference": "prepare_success",
                "jet_id": jet.id,
                "waypoint_template_id": waypoint_template.id,
                "state": "draft",
            }
        )

        # Manager should be able to prepare with write access
        try:
            result = record.with_user(self.manager).prepare()
            self.assertTrue(result, "Manager should be able to prepare")
            record.invalidate_recordset()
            # State should be ready (no plan_create_id)
            self.assertEqual(record.state, "ready", "State should be ready")
        except AccessError:
            self.fail(
                "Manager should be able to prepare when in template's manager_ids"
            )

    def test_manager_fly_to_success_with_write_access(self):
        """Test Manager: Can fly_to waypoint with write access"""
        # Create jet template with manager in manager_ids
        jet_template = self.JetTemplate.create(
            {
                "name": "Test Template",
                "reference": "test_template",
                "manager_ids": [(4, self.manager.id)],
            }
        )

        # Ensure manager has server access
        self.server_test_1.write({"user_ids": [(4, self.manager.id)]})

        # Create jet from this template with manager in manager_ids
        jet = self._create_jet(
            name="Fly To Success Jet",
            reference="fly_to_success_jet",
            template=jet_template,
            server=self.server_test_1,
            manager_ids=[(4, self.manager.id)],
        )

        # Create waypoint template
        waypoint_template = self.JetWaypointTemplate.create(
            {
                "name": "Test Waypoint Template",
                "reference": "test_waypoint_template",
                "jet_template_id": jet_template.id,
            }
        )

        record = self.JetWaypoint.create(
            {
                "name": "Fly To Success",
                "reference": "fly_to_success",
                "jet_id": jet.id,
                "waypoint_template_id": waypoint_template.id,
                "state": "ready",
            }
        )

        # Manager should be able to fly_to with write access
        try:
            result = record.with_user(self.manager).fly_to()
            self.assertTrue(result, "Manager should be able to fly_to")
            record.invalidate_recordset()
            # State should be current (no previous waypoint, no plan_arrive_id)
            self.assertEqual(record.state, "current", "State should be current")
        except AccessError:
            self.fail("Manager should be able to fly_to when in template's manager_ids")
