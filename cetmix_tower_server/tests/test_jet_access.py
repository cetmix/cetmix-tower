# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError

from .common_jets import TestTowerJetsCommon


class TestTowerJetAccess(TestTowerJetsCommon):
    """
    Test access rules for Jet model
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create additional manager for multi-manager tests
        cls.manager2 = cls.Users.create(
            {
                "name": "Test Manager 2",
                "login": "test_manager_2",
                "email": "test_manager_2@example.com",
                "groups_id": [(6, 0, [cls.group_manager.id])],
            }
        )

        # Create additional server for testing
        cls.server_test_2 = cls.Server.create(
            {
                "name": "Test Server 2",
                "ip_v4_address": "127.0.0.3",
                "ssh_username": "test",
                "ssh_password": "test",
                "user_ids": [(5, 0, 0)],
                "manager_ids": [(5, 0, 0)],
            }
        )

    # ======================
    # User Read Access Tests
    # ======================

    def test_user_read_access_jet_user_server_user(self):
        """Test User: Read when user in jet user_ids AND server user_ids"""
        jet = self._create_jet(
            "User Jet",
            "user_jet",
            user_ids=[(4, self.user.id)],
            server_user_ids=[(4, self.user.id)],
        )

        records = self.Jet.with_user(self.user).search([("id", "=", jet.id)])
        self.assertIn(
            jet,
            records,
            "User should read when in jet user_ids AND server user_ids",
        )

    def test_user_read_no_access_jet_user_only(self):
        """Test User: No read when user in jet user_ids but NOT in server user_ids"""
        jet = self._create_jet(
            "User Jet No Server",
            "user_jet_no_server",
            user_ids=[(4, self.user.id)],
            server_user_ids=[(5, 0, 0)],
        )

        records = self.Jet.with_user(self.user).search([("id", "=", jet.id)])
        self.assertEqual(
            len(records),
            0,
            "User should not read when not in server user_ids",
        )

    def test_user_read_no_access_server_user_only(self):
        """Test User: No read when user in server user_ids but NOT in jet user_ids"""
        jet = self._create_jet(
            "Server User No Jet",
            "server_user_no_jet",
            user_ids=[(5, 0, 0)],
            server_user_ids=[(4, self.user.id)],
        )

        records = self.Jet.with_user(self.user).search([("id", "=", jet.id)])
        self.assertEqual(
            len(records),
            0,
            "User should not read when not in jet user_ids",
        )

    def test_user_write_forbidden(self):
        """Test User: Cannot write/create/delete records"""
        jet = self._create_jet(
            "User Jet",
            "user_jet",
            user_ids=[(4, self.user.id)],
            server_user_ids=[(4, self.user.id)],
        )

        # User should not be able to write
        with self.assertRaises(AccessError):
            jet.with_user(self.user).write({"name": "Updated Name"})

        # User should not be able to create
        with self.assertRaises(AccessError):
            self.Jet.with_user(self.user).create(
                {
                    "name": "New Jet",
                    "reference": "new_jet",
                    "jet_template_id": self.jet_template_test.id,
                    "server_id": self.server_test_1.id,
                }
            )

        # User should not be able to delete
        # Jet is deletable by default, so this tests access control
        with self.assertRaises(AccessError):
            jet.with_user(self.user).unlink()

    # ======================
    # Manager Read Access Tests
    # ======================

    def test_manager_read_access_jet_user_server_user(self):
        """Test Manager: Read when in jet user_ids AND server user_ids"""
        jet = self._create_jet(
            "Manager Jet User",
            "manager_jet_user",
            user_ids=[(4, self.manager.id)],
            server_user_ids=[(4, self.manager.id)],
        )

        records = self.Jet.with_user(self.manager).search([("id", "=", jet.id)])
        self.assertIn(
            jet,
            records,
            "Manager should read when in jet user_ids AND server user_ids",
        )

    def test_manager_read_access_jet_manager_server_manager(self):
        """Test Manager: Read when in jet manager_ids AND server manager_ids"""
        jet = self._create_jet(
            "Manager Jet Manager",
            "manager_jet_manager",
            manager_ids=[(4, self.manager.id)],
            server_manager_ids=[(4, self.manager.id)],
        )

        records = self.Jet.with_user(self.manager).search([("id", "=", jet.id)])
        self.assertIn(
            jet,
            records,
            "Manager should read when in jet manager_ids AND server manager_ids",
        )

    def test_manager_read_access_jet_user_server_manager(self):
        """Test Manager: Read when in jet user_ids AND server manager_ids"""
        jet = self._create_jet(
            "Manager Jet User Server Manager",
            "manager_jet_user_server_manager",
            user_ids=[(4, self.manager.id)],
            server_manager_ids=[(4, self.manager.id)],
        )

        records = self.Jet.with_user(self.manager).search([("id", "=", jet.id)])
        self.assertIn(
            jet,
            records,
            "Manager should read when in jet user_ids AND server manager_ids",
        )

    def test_manager_read_access_jet_manager_server_user(self):
        """Test Manager: Read when in jet manager_ids AND server user_ids"""
        jet = self._create_jet(
            "Manager Jet Manager Server User",
            "manager_jet_manager_server_user",
            manager_ids=[(4, self.manager.id)],
            server_user_ids=[(4, self.manager.id)],
        )

        records = self.Jet.with_user(self.manager).search([("id", "=", jet.id)])
        self.assertIn(
            jet,
            records,
            "Manager should read when in jet manager_ids AND server user_ids",
        )

    def test_manager_read_no_access_jet_only(self):
        """Test Manager: No read when in jet but NOT in server"""
        jet = self._create_jet(
            "Manager Jet No Server",
            "manager_jet_no_server",
            user_ids=[(4, self.manager.id)],
            server_user_ids=[(5, 0, 0)],
            server_manager_ids=[(5, 0, 0)],
        )

        records = self.Jet.with_user(self.manager).search([("id", "=", jet.id)])
        self.assertEqual(
            len(records),
            0,
            "Manager should not read when not in server user_ids or manager_ids",
        )

    def test_manager_read_no_access_server_only(self):
        """Test Manager: No read when in server but NOT in jet"""
        jet = self._create_jet(
            "Manager Server No Jet",
            "manager_server_no_jet",
            user_ids=[(5, 0, 0)],
            manager_ids=[(5, 0, 0)],
            server_user_ids=[(4, self.manager.id)],
        )

        records = self.Jet.with_user(self.manager).search([("id", "=", jet.id)])
        self.assertEqual(
            len(records),
            0,
            "Manager should not read when not in jet user_ids or manager_ids",
        )

    # ======================
    # Manager Write/Create Access Tests
    # ======================

    def test_manager_write_access_jet_manager_server_user(self):
        """Test Manager: Write when in jet manager_ids AND server user_ids"""
        jet = self._create_jet(
            "Manager Write Jet",
            "manager_write_jet",
            manager_ids=[(4, self.manager.id)],
            server_user_ids=[(4, self.manager.id)],
        )

        try:
            jet.with_user(self.manager).write({"name": "Updated Name"})
            jet.invalidate_recordset()
            self.assertEqual(
                jet.name, "Updated Name", "Manager should be able to update"
            )
        except AccessError:
            self.fail(
                "Manager should be able to update when in jet"
                " manager_ids AND server user_ids.",
            )

    def test_manager_write_access_jet_manager_server_manager(self):
        """Test Manager: Write when in jet manager_ids AND server manager_ids"""
        jet = self._create_jet(
            "Manager Write Jet Manager",
            "manager_write_jet_manager",
            manager_ids=[(4, self.manager.id)],
            server_manager_ids=[(4, self.manager.id)],
        )

        try:
            jet.with_user(self.manager).write({"name": "Updated"})
        except AccessError:
            self.fail(
                "Manager should be able to write when in jet"
                " manager_ids AND server manager_ids.",
            )

    def test_manager_write_forbidden_not_in_jet_manager_ids(self):
        """Test Manager: No write when NOT in jet manager_ids"""
        jet = self._create_jet(
            "Manager No Write Jet",
            "manager_no_write_jet",
            user_ids=[(4, self.manager.id)],  # Only in user_ids, not manager_ids
            server_user_ids=[(4, self.manager.id)],
        )

        with self.assertRaises(AccessError):
            jet.with_user(self.manager).write({"name": "Should Fail"})

    def test_manager_write_forbidden_not_in_server(self):
        """Test Manager: No write when in jet manager_ids but NOT in server"""
        jet = self._create_jet(
            "Manager No Write Server",
            "manager_no_write_server",
            manager_ids=[(4, self.manager.id)],
            server_user_ids=[(5, 0, 0)],
            server_manager_ids=[(5, 0, 0)],
        )

        with self.assertRaises(AccessError):
            jet.with_user(self.manager).write({"name": "Should Fail"})

    def test_manager_create_access(self):
        """
        Test Manager:
        Create when in jet manager_ids AND server user_ids or manager_ids.
        """
        # Create with manager in jet manager_ids and server user_ids - should succeed
        try:
            jet = self._create_jet(
                "Create Success",
                "create_success",
                user_ids=[(5, 0, 0)],
                manager_ids=[(4, self.manager.id)],
                server_user_ids=[(4, self.manager.id)],
                with_user=self.manager,
            )
            records = self.Jet.search([("id", "=", jet.id)])
            self.assertIn(jet, records, "Manager should be able to create")
        except AccessError:
            self.fail("Manager should be able to create when in jet manager_ids")

    def test_manager_create_forbidden_not_in_manager_ids(self):
        """Test Manager: Cannot create when not in jet manager_ids"""
        # Configure server access first (required, but jet manager_ids check will fail)
        self.server_test_1.write({"user_ids": [(4, self.manager.id)]})

        with self.assertRaises(AccessError):
            self.Jet.with_user(self.manager).create(
                {
                    "name": "Create Fail",
                    "reference": "create_fail",
                    "jet_template_id": self.jet_template_test.id,
                    "server_id": self.server_test_1.id,
                    "user_ids": [
                        (4, self.manager.id)
                    ],  # Only user_ids, not manager_ids
                    "manager_ids": [(5, 0, 0)],
                }
            )

    # ======================
    # Manager Delete Access Tests
    # ======================

    def test_manager_delete_own_record(self):
        """Test Manager: Delete own record when in jet manager_ids AND server"""
        # Create as manager to ensure create_uid is set correctly
        jet = self._create_jet(
            "My Jet",
            "my_jet",
            manager_ids=[(4, self.manager.id)],
            server_user_ids=[(4, self.manager.id)],
            with_user=self.manager,
        )
        # Jet is deletable by default, so manager can delete it
        try:
            jet.with_user(self.manager).unlink()
            records = self.Jet.search([("id", "=", jet.id)])
            self.assertEqual(
                len(records), 0, "Manager should be able to delete own record"
            )
        except AccessError:
            self.fail("Manager should be able to delete own record")

    def test_manager_delete_not_creator(self):
        """Test Manager: Cannot delete record created by another user"""
        jet = self._create_jet(
            "Other's Jet",
            "others_jet",
            manager_ids=[(4, self.manager.id), (4, self.manager2.id)],
            server_user_ids=[(4, self.manager.id), (4, self.manager2.id)],
            with_user=self.manager2,
        )

        # Manager1 cannot delete Manager2's record
        # Jet is deletable by default, so this tests access control
        with self.assertRaises(AccessError):
            jet.with_user(self.manager).unlink()

    def test_manager_delete_not_in_manager_ids(self):
        """Test Manager: Cannot delete when not in jet manager_ids"""
        jet = self._create_jet(
            "Removed Manager",
            "removed_manager",
            manager_ids=[(4, self.manager.id)],
            server_user_ids=[(4, self.manager.id)],
            with_user=self.manager,
        )
        # Remove from manager_ids
        jet.write({"manager_ids": [(5, 0, 0)]})

        # Cannot delete anymore
        # Jet is deletable by default, so this tests access control
        with self.assertRaises(AccessError):
            jet.with_user(self.manager).unlink()

    def test_manager_delete_not_in_server(self):
        """Test Manager: Cannot delete when in jet manager_ids but NOT in server"""
        jet = self._create_jet(
            "Manager Jet",
            "manager_jet",
            manager_ids=[(4, self.manager.id)],
            server_user_ids=[(4, self.manager.id)],
            with_user=self.manager,
        )
        # Remove server access
        self.server_test_1.write({"user_ids": [(5, 0, 0)], "manager_ids": [(5, 0, 0)]})

        # Cannot delete anymore
        # Jet is deletable by default, so this tests access control
        with self.assertRaises(AccessError):
            jet.with_user(self.manager).unlink()

    # ======================
    # Root Access Tests
    # ======================

    def test_root_full_access(self):
        """Test Root: Full CRUD access regardless of access restrictions"""
        # Test Root can create
        jet = self.Jet.create(
            {
                "name": "Root Jet",
                "reference": "root_jet",
                "jet_template_id": self.jet_template_test.id,
                "server_id": self.server_test_1.id,
                "user_ids": [(5, 0, 0)],
                "manager_ids": [(5, 0, 0)],
            }
        )

        # Root can read
        records = self.Jet.search([("id", "=", jet.id)])
        self.assertIn(jet, records, "Root should be able to read")

        # Root can write
        jet.write({"name": "Root Updated Jet"})
        jet.invalidate_recordset()
        self.assertEqual(jet.name, "Root Updated Jet", "Root should be able to update")

        # Test Root can delete records created by other users
        manager_jet = self._create_jet(
            "Manager's Jet",
            "managers_jet",
            manager_ids=[(4, self.manager.id)],
            server_user_ids=[(4, self.manager.id)],
            with_user=self.manager,
        )
        # Jet is deletable by default, so root can delete it
        manager_jet.unlink()
        records = self.Jet.search([("id", "=", manager_jet.id)])
        self.assertEqual(
            len(records), 0, "Root should be able to delete records from any creator"
        )
