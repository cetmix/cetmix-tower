# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError

from .common_jets import TestTowerJetsCommon


class TestTowerJetTemplateAccess(TestTowerJetsCommon):
    """
    Test access rules for Jet Template model
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
    # User Access Tests
    # ======================

    def test_user_read_access_level_user(self):
        """Test User: Read access when access_level is "User" (1)"""
        record = self.JetTemplate.create(
            {
                "name": "User Level Template",
                "reference": "user_level_template",
                "access_level": "1",  # User level
                "user_ids": False,  # No users initially
                "manager_ids": False,  # No managers initially
            }
        )

        # User should be able to read when access_level is "User"
        records = self.JetTemplate.with_user(self.user).search([("id", "=", record.id)])
        self.assertEqual(
            len(records),
            1,
            "User should be able to read record when access_level is 'User'",
        )

    def test_user_read_access_user_ids(self):
        """Test User: Read access when user is added in user_ids"""
        record = self.JetTemplate.create(
            {
                "name": "User Added Template",
                "reference": "user_added_template",
                "access_level": "2",  # Manager level - normally not accessible
                "user_ids": [(4, self.user.id)],  # User added
                "manager_ids": False,
            }
        )

        # User should be able to read when added to user_ids
        records = self.JetTemplate.with_user(self.user).search([("id", "=", record.id)])
        self.assertEqual(
            len(records),
            1,
            "User should be able to read record when added to user_ids",
        )

    def test_user_read_access_jet_user_ids(self):
        """
        Test User: Read access when user is added in "Users" of any Jets
        created from the template
        """
        # Create template with Manager level - normally not accessible
        # and user NOT in template's user_ids
        template = self.JetTemplate.create(
            {
                "name": "Template with Jet Users",
                "reference": "template_with_jet_users",
                "access_level": "2",  # Manager level - normally not accessible
                "user_ids": False,  # No users in template
                "manager_ids": False,
            }
        )

        # User should NOT be able to read initially
        records = self.JetTemplate.with_user(self.user).search(
            [("id", "=", template.id)]
        )
        self.assertEqual(
            len(records),
            0,
            "User should not be able to read template without access",
        )

        # Create a Jet from this template
        # Need to add server to template's server_ids for jet creation
        template.write({"server_ids": [(4, self.server_test_1.id)]})
        self._create_jet(
            name="Test Jet from Template",
            reference="test_jet_from_template",
            template=template,
            server=self.server_test_1,
            user_ids=[(4, self.user.id)],  # Add user to Jet's user_ids
        )

        # User should now be able to read the template
        records = self.JetTemplate.with_user(self.user).search(
            [("id", "=", template.id)]
        )
        self.assertEqual(
            len(records),
            1,
            "User should be able to read template when added to Jet's user_ids",
        )

    def test_user_read_no_access(self):
        """
        Test User: No read access when access_level is higher,
        user not in template's user_ids, and user not in any Jet's user_ids
        """
        record = self.JetTemplate.create(
            {
                "name": "Manager Level Template",
                "reference": "manager_level_template",
                "access_level": "2",  # Manager level
                "user_ids": False,  # No users
                "manager_ids": False,
            }
        )

        # User should not be able to read
        # (no access via access_level, template user_ids, or jet user_ids)
        records = self.JetTemplate.with_user(self.user).search([("id", "=", record.id)])
        self.assertEqual(
            len(records),
            0,
            "User should not see record with Manager level "
            "when not in user_ids or jet user_ids",
        )

    def test_user_write_forbidden(self):
        """Test User: Cannot write/create/delete records"""
        record = self.JetTemplate.create(
            {
                "name": "User Template",
                "reference": "user_template",
                "access_level": "1",
                "user_ids": [(4, self.user.id)],
            }
        )

        # User should not be able to write
        with self.assertRaises(AccessError):
            record.with_user(self.user).write({"name": "Updated Name"})

        # User should not be able to create
        with self.assertRaises(AccessError):
            self.JetTemplate.with_user(self.user).create(
                {"name": "New Template", "reference": "new_template"}
            )

        # User should not be able to delete
        with self.assertRaises(AccessError):
            record.with_user(self.user).unlink()

    # ======================
    # Manager Read Access Tests
    # ======================

    def test_manager_read_access_level_user(self):
        """Test Manager: Read when access_level is "User" (1)"""
        record = self.JetTemplate.create(
            {
                "name": "User Level for Manager",
                "reference": "user_level_manager",
                "access_level": "1",
                "user_ids": False,
                "manager_ids": False,
            }
        )

        records = self.JetTemplate.with_user(self.manager).search(
            [("id", "=", record.id)]
        )
        self.assertEqual(len(records), 1, "Manager should read access_level='1'")

    def test_manager_read_access_level_manager(self):
        """Test Manager: Read when access_level is "Manager" (2)"""
        record = self.JetTemplate.create(
            {
                "name": "Manager Level",
                "reference": "manager_level",
                "access_level": "2",
                "user_ids": False,
                "manager_ids": False,
            }
        )

        records = self.JetTemplate.with_user(self.manager).search(
            [("id", "=", record.id)]
        )
        self.assertEqual(len(records), 1, "Manager should read access_level='2'")

    def test_manager_read_access_user_ids(self):
        """Test Manager: Read when added to user_ids regardless of access_level"""
        record = self.JetTemplate.create(
            {
                "name": "Manager in Users",
                "reference": "manager_in_users",
                "access_level": "3",  # Root level - normally not accessible
                "user_ids": [(4, self.manager.id)],  # Manager added as user
                "manager_ids": False,
            }
        )

        records = self.JetTemplate.with_user(self.manager).search(
            [("id", "=", record.id)]
        )
        self.assertEqual(len(records), 1, "Manager should read when in user_ids")

    def test_manager_read_no_access_root_level(self):
        """Test Manager: No read access for Root level (3) without user_ids"""
        record = self.JetTemplate.create(
            {
                "name": "Root Level",
                "reference": "root_level",
                "access_level": "3",
                "user_ids": False,
                "manager_ids": False,
            }
        )

        records = self.JetTemplate.with_user(self.manager).search(
            [("id", "=", record.id)]
        )
        self.assertEqual(len(records), 0, "Manager should not read access_level='3'")

    # ======================
    # Manager Write/Create Access Tests
    # ======================

    def test_manager_write_access_level_and_manager_ids(self):
        """Test Manager: Write when access_level <= 2 AND in manager_ids"""
        record = self.JetTemplate.create(
            {
                "name": "Manager Can Write",
                "reference": "manager_can_write",
                "access_level": "2",
                "user_ids": False,
                "manager_ids": [(4, self.manager.id)],  # Manager added
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
            self.fail("Manager should be able to update when in manager_ids")

    def test_manager_write_access_level_user(self):
        """Test Manager: Write when access_level = 1 and in manager_ids"""
        record = self.JetTemplate.create(
            {
                "name": "User Level Manager Write",
                "reference": "user_level_manager_write",
                "access_level": "1",
                "user_ids": False,
                "manager_ids": [(4, self.manager.id)],
            }
        )

        try:
            record.with_user(self.manager).write({"name": "Updated"})
        except AccessError:
            self.fail("Manager should be able to write access_level='1'")

    def test_manager_write_forbidden_not_in_manager_ids(self):
        """Test Manager: No write when not in manager_ids"""
        record = self.JetTemplate.create(
            {
                "name": "No Write Access",
                "reference": "no_write_access",
                "access_level": "2",
                "user_ids": [(4, self.manager.id)],  # Only in user_ids, not manager_ids
                "manager_ids": False,
            }
        )

        with self.assertRaises(AccessError):
            record.with_user(self.manager).write({"name": "Should Fail"})

    def test_manager_write_forbidden_root_level(self):
        """Test Manager: No write when access_level is Root (3)"""
        record = self.JetTemplate.create(
            {
                "name": "Root Level No Write",
                "reference": "root_level_no_write",
                "access_level": "3",
                "user_ids": [(4, self.manager.id)],
                "manager_ids": [(4, self.manager.id)],  # In manager_ids
            }
        )

        with self.assertRaises(AccessError):
            record.with_user(self.manager).write({"name": "Should Fail"})

    def test_manager_create_access(self):
        """Test Manager: Create when access_level <= 2 AND in manager_ids"""
        # Try to create without adding to manager_ids - should fail
        with self.assertRaises(AccessError):
            self.JetTemplate.with_user(self.manager).create(
                {
                    "name": "Create Fail",
                    "reference": "create_fail",
                    "access_level": "2",
                    "manager_ids": False,  # Not in manager_ids
                }
            )

        # Create with manager added - should succeed
        try:
            record = self.JetTemplate.with_user(self.manager).create(
                {
                    "name": "Create Success",
                    "reference": "create_success",
                    "access_level": "2",
                    "manager_ids": [(4, self.manager.id)],  # In manager_ids
                }
            )
            records = self.JetTemplate.search([("id", "=", record.id)])
            self.assertEqual(len(records), 1, "Manager should be able to create")
        except AccessError:
            self.fail("Manager should be able to create when in manager_ids")

    # ======================
    # Manager Delete Access Tests
    # ======================

    def test_manager_delete_own_record(self):
        """Test Manager: Delete own record when in manager_ids"""
        record = self.JetTemplate.with_user(self.manager).create(
            {
                "name": "My Record",
                "reference": "my_record",
                "access_level": "2",
                "manager_ids": [(4, self.manager.id)],
            }
        )

        try:
            record.with_user(self.manager).unlink()
            records = self.JetTemplate.search([("id", "=", record.id)])
            self.assertEqual(
                len(records), 0, "Manager should be able to delete own record"
            )
        except AccessError:
            self.fail("Manager should be able to delete own record")

    def test_manager_delete_not_creator(self):
        """Test Manager: Cannot delete record created by another user"""
        record = self.JetTemplate.with_user(self.manager2).create(
            {
                "name": "Other's Record",
                "reference": "others_record",
                "access_level": "2",
                "manager_ids": [(4, self.manager.id), (4, self.manager2.id)],
            }
        )

        # Manager1 cannot delete Manager2's record
        with self.assertRaises(AccessError):
            record.with_user(self.manager).unlink()

    def test_manager_delete_not_in_manager_ids(self):
        """Test Manager: Cannot delete when not in manager_ids"""
        record = self.JetTemplate.with_user(self.manager).create(
            {
                "name": "Removed Manager",
                "reference": "removed_manager",
                "access_level": "2",
                "manager_ids": [(4, self.manager.id)],
            }
        )

        # Remove from manager_ids
        record.write({"manager_ids": False})

        # Cannot delete anymore
        with self.assertRaises(AccessError):
            record.with_user(self.manager).unlink()

    def test_manager_delete_root_level(self):
        """Test Manager: Cannot delete Root level record"""
        # Create record with Root level as root (default user)
        record = self.JetTemplate.create(
            {
                "name": "Root Level Delete",
                "reference": "root_level_delete",
                "access_level": "3",  # Root level
                "manager_ids": [(4, self.manager.id)],
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
        # Test CRUD operations for all access levels
        for access_level in ["1", "2", "3"]:
            # Root can create any level
            record = self.JetTemplate.with_user(self.root).create(
                {
                    "name": f"Root Level {access_level}",
                    "reference": f"root_level_{access_level}",
                    "access_level": access_level,
                    "user_ids": False,
                    "manager_ids": False,
                }
            )

            # Root can read any level
            records = self.JetTemplate.with_user(self.root).search(
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
        manager_record = self.JetTemplate.with_user(self.manager).create(
            {
                "name": "Manager's Record",
                "reference": "managers_record",
                "access_level": "2",
                "manager_ids": [(4, self.manager.id)],
            }
        )
        manager_record.with_user(self.root).unlink()
        records = self.JetTemplate.with_user(self.root).search(
            [("id", "=", manager_record.id)]
        )
        self.assertEqual(
            len(records), 0, "Root should be able to delete records from any creator"
        )

    # ======================
    # Edge Cases
    # ======================

    def test_access_level_changes_visibility(self):
        """Test that changing access_level affects visibility"""
        # Create with User level
        record = self.JetTemplate.create(
            {
                "name": "Changing Level",
                "reference": "changing_level",
                "access_level": "1",
                "user_ids": False,
                "manager_ids": False,
            }
        )

        # User can read
        records = self.JetTemplate.with_user(self.user).search([("id", "=", record.id)])
        self.assertEqual(len(records), 1, "User should read level 1")

        # Change to Root level
        record.write({"access_level": "3"})

        # User cannot read anymore
        records = self.JetTemplate.with_user(self.user).search([("id", "=", record.id)])
        self.assertEqual(len(records), 0, "User should not read level 3")

    def test_multiple_managers_access(self):
        """Test multiple managers accessing the same record"""
        record = self.JetTemplate.with_user(self.manager).create(
            {
                "name": "Multi Manager",
                "reference": "multi_manager",
                "access_level": "2",
                "manager_ids": [(4, self.manager.id), (4, self.manager2.id)],
            }
        )

        # Both managers should be able to read
        records1 = self.JetTemplate.with_user(self.manager).search(
            [("id", "=", record.id)]
        )
        records2 = self.JetTemplate.with_user(self.manager2).search(
            [("id", "=", record.id)]
        )
        self.assertEqual(len(records1), 1, "Manager1 should read")
        self.assertEqual(len(records2), 1, "Manager2 should read")

        # Both can write
        record.with_user(self.manager).write({"name": "Manager1 Update"})
        record.with_user(self.manager2).write({"name": "Manager2 Update"})

        # Only creator can delete
        with self.assertRaises(AccessError):
            record.with_user(self.manager2).unlink()

        # Creator can delete
        record = self.JetTemplate.with_user(self.manager).create(
            {
                "name": "Creator Delete",
                "reference": "creator_delete",
                "access_level": "2",
                "manager_ids": [(4, self.manager.id), (4, self.manager2.id)],
            }
        )
        try:
            record.with_user(self.manager).unlink()
        except AccessError:
            self.fail("Creator should be able to delete")
