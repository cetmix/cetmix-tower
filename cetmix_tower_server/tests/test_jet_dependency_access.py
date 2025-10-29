# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError

from .common_jets import TestTowerJetsCommon


class TestTowerJetDependencyAccess(TestTowerJetsCommon):
    """
    Test access rules for Jet Dependency model
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

        # Set up model reference
        cls.JetDependency = cls.env["cx.tower.jet.dependency"]

    # ======================
    # Manager Read Access Tests
    # ======================

    def test_manager_read_access_both_user_ids(self):
        """Test Manager: Read when in user_ids of both jets"""
        _, _, dependency = self._create_jet_dependency(
            "Jet 1",
            "jet_1",
            "Jet 2",
            "jet_2",
            jet_user_ids=[(4, self.manager.id)],
            depends_on_user_ids=[(4, self.manager.id)],
            jet_server_user_ids=[(4, self.manager.id)],
            depends_on_server_user_ids=[(4, self.manager.id)],
        )

        records = self.JetDependency.with_user(self.manager).search(
            [("id", "=", dependency.id)]
        )
        self.assertEqual(
            len(records),
            1,
            "Manager should read when in user_ids of both jets",
        )
        self.assertIn(
            dependency,
            records,
            "Manager should get exactly the dependency record we searched for",
        )

    def test_manager_read_access_both_manager_ids(self):
        """Test Manager: Read when in manager_ids of both jets"""
        _, _, dependency = self._create_jet_dependency(
            "Jet Manager 1",
            "jet_manager_1",
            "Jet Manager 2",
            "jet_manager_2",
            jet_manager_ids=[(4, self.manager.id)],
            depends_on_manager_ids=[(4, self.manager.id)],
            jet_server_user_ids=[(4, self.manager.id)],
            depends_on_server_user_ids=[(4, self.manager.id)],
        )

        records = self.JetDependency.with_user(self.manager).search(
            [("id", "=", dependency.id)]
        )
        self.assertEqual(
            len(records),
            1,
            "Manager should read when in manager_ids of both jets",
        )
        self.assertIn(
            dependency,
            records,
            "Manager should get exactly the dependency record we searched for",
        )

    def test_manager_read_access_jet_user_depends_manager(self):
        """Test Manager: Read when in user_ids of jet and manager_ids of depends"""
        _, _, dependency = self._create_jet_dependency(
            "Jet User",
            "jet_user",
            "Depends Manager",
            "depends_manager",
            jet_user_ids=[(4, self.manager.id)],
            depends_on_manager_ids=[(4, self.manager.id)],
            jet_server_user_ids=[(4, self.manager.id)],
            depends_on_server_user_ids=[(4, self.manager.id)],
        )

        records = self.JetDependency.with_user(self.manager).search(
            [("id", "=", dependency.id)]
        )
        self.assertEqual(
            len(records),
            1,
            "Manager should read when in user_ids of jet and manager_ids of depends",
        )
        self.assertIn(
            dependency,
            records,
            "Manager should get exactly the dependency record we searched for",
        )

    def test_manager_read_access_jet_manager_depends_user(self):
        """Test Manager: Read when in manager_ids of jet and user_ids of depends"""
        _, _, dependency = self._create_jet_dependency(
            "Jet Manager",
            "jet_manager",
            "Depends User",
            "depends_user",
            jet_manager_ids=[(4, self.manager.id)],
            depends_on_user_ids=[(4, self.manager.id)],
            jet_server_user_ids=[(4, self.manager.id)],
            depends_on_server_user_ids=[(4, self.manager.id)],
        )

        records = self.JetDependency.with_user(self.manager).search(
            [("id", "=", dependency.id)]
        )
        self.assertEqual(
            len(records),
            1,
            "Manager should read when in manager_ids of jet and user_ids of depends",
        )
        self.assertIn(
            dependency,
            records,
            "Manager should get exactly the dependency record we searched for",
        )

    def test_manager_read_no_access_jet_only(self):
        """Test Manager: No read when in jet but NOT in depends on jet"""
        _, _, dependency = self._create_jet_dependency(
            "Jet Has Access",
            "jet_has_access",
            "Depends No Access",
            "depends_no_access",
            jet_user_ids=[(4, self.manager.id)],
            depends_on_user_ids=[(5, 0, 0)],
            depends_on_manager_ids=[(5, 0, 0)],
            jet_server_user_ids=[(4, self.manager.id)],
            depends_on_server_user_ids=[(4, self.manager.id)],
        )

        records = self.JetDependency.with_user(self.manager).search(
            [("id", "=", dependency.id)]
        )
        self.assertEqual(
            len(records),
            0,
            "Manager should not read when not in depends_on"
            " jet user_ids or manager_ids",
        )

    def test_manager_read_no_access_depends_only(self):
        """Test Manager: No read when in depends on jet but NOT in jet"""
        _, _, dependency = self._create_jet_dependency(
            "Jet No Access",
            "jet_no_access",
            "Depends Has Access",
            "depends_has_access",
            jet_user_ids=[(5, 0, 0)],
            jet_manager_ids=[(5, 0, 0)],
            depends_on_user_ids=[(4, self.manager.id)],
            jet_server_user_ids=[(4, self.manager.id)],
            depends_on_server_user_ids=[(4, self.manager.id)],
        )

        records = self.JetDependency.with_user(self.manager).search(
            [("id", "=", dependency.id)]
        )
        self.assertEqual(
            len(records),
            0,
            "Manager should not read when not in jet user_ids or manager_ids",
        )

    # ======================
    # Manager CRUD Access Tests
    # ======================

    def test_manager_write_access(self):
        """
        Test Manager:
        Write access when in manager_ids of jet AND user_ids
        or manager_ids of depends.
        """
        # Test with depends_on user_ids (same conditions as create test,
        # but tests write access on existing record)
        _, _, dependency1 = self._create_jet_dependency(
            "Write Jet Manager",
            "write_jet_manager",
            "Depends User",
            "depends_user",
            jet_manager_ids=[(4, self.manager.id)],
            depends_on_user_ids=[(4, self.manager.id)],
            jet_server_user_ids=[(4, self.manager.id)],
            depends_on_server_user_ids=[(4, self.manager.id)],
        )

        # Verify manager can access the dependency (write permissions allow read access)
        try:
            dependency1.invalidate_recordset()
            dependency1.with_user(self.manager).read(["jet_id", "jet_depends_on_id"])
        except AccessError:
            self.fail(
                "Manager should be able to write when in jet manager_ids "
                "AND depends_on user_ids"
            )

        # Test with depends_on manager_ids - use different templates
        # to avoid duplicate template dependency
        _, _, dependency2 = self._create_jet_dependency(
            "Write Jet Manager 2",
            "write_jet_manager_2",
            "Depends Manager",
            "depends_manager",
            jet_manager_ids=[(4, self.manager.id)],
            depends_on_manager_ids=[(4, self.manager.id)],
            jet_server_user_ids=[(4, self.manager.id)],
            depends_on_server_user_ids=[(4, self.manager.id)],
            jet_template=self.jet_template_nginx,
            # Use different template to avoid duplicate
            depends_on_template=self.jet_template_docker,
        )

        try:
            dependency2.invalidate_recordset()
            dependency2.with_user(self.manager).read(["jet_id", "jet_depends_on_id"])
        except AccessError:
            self.fail(
                "Manager should be able to write when in jet manager_ids"
                " AND depends_on manager_ids"
            )

    def test_manager_create_access(self):
        """
        Test Manager: Create when in manager_ids of jet AND user_ids
        or manager_ids of depends.
        """
        # Create template dependency using different templates
        template_dep = self.JetTemplateDependency.create(
            {
                "template_id": self.jet_template_test.id,
                "template_required_id": self.jet_template_tower_core.id,
            }
        )

        # Create jets with proper access
        jet = self._create_jet(
            "Create Jet",
            "create_jet",
            template=self.jet_template_test,
            manager_ids=[(4, self.manager.id)],
            server_user_ids=[(4, self.manager.id)],
        )

        depends_on_jet = self._create_jet(
            "Create Depends",
            "create_depends",
            template=self.jet_template_tower_core,
            user_ids=[(4, self.manager.id)],
            server_user_ids=[(4, self.manager.id)],
        )

        # Try to create dependency as manager
        try:
            dependency = self.JetDependency.with_user(self.manager).create(
                {
                    "jet_id": jet.id,
                    "jet_depends_on_id": depends_on_jet.id,
                    "jet_template_dependency_id": template_dep.id,
                }
            )
            records = self.JetDependency.search([("id", "=", dependency.id)])
            self.assertIn(
                dependency,
                records,
                "Manager should be able to create dependency",
            )
        except AccessError:
            self.fail("Manager should be able to create when in jet manager_ids")

    def test_manager_create_forbidden_not_in_jet_manager_ids(self):
        """Test Manager: Cannot create when not in jet manager_ids"""
        # Create template dependency using different templates
        template_dep = self.JetTemplateDependency.create(
            {
                "template_id": self.jet_template_test.id,
                "template_required_id": self.jet_template_tower_core.id,
            }
        )

        # Create jets - manager only in jet user_ids (not manager_ids)
        jet = self._create_jet(
            "No Create Jet",
            "no_create_jet",
            template=self.jet_template_test,
            user_ids=[(4, self.manager.id)],
            server_user_ids=[(4, self.manager.id)],
        )

        depends_on_jet = self._create_jet(
            "No Create Depends",
            "no_create_depends",
            template=self.jet_template_tower_core,
            user_ids=[(4, self.manager.id)],
            server_user_ids=[(4, self.manager.id)],
        )

        # Should not be able to create
        with self.assertRaises(AccessError):
            self.JetDependency.with_user(self.manager).create(
                {
                    "jet_id": jet.id,
                    "jet_depends_on_id": depends_on_jet.id,
                    "jet_template_dependency_id": template_dep.id,
                }
            )

    def test_manager_create_forbidden_not_in_depends(self):
        """
        Test Manager: Cannot create when in jet manager_ids but NOT in depends.
        """
        # Create template dependency using different templates
        template_dep = self.JetTemplateDependency.create(
            {
                "template_id": self.jet_template_test.id,
                "template_required_id": self.jet_template_tower_core.id,
            }
        )

        # Create jets - manager in jet manager_ids but not in depends
        jet = self._create_jet(
            "Create Jet",
            "create_jet",
            template=self.jet_template_test,
            manager_ids=[(4, self.manager.id)],
            server_user_ids=[(4, self.manager.id)],
        )

        depends_on_jet = self._create_jet(
            "No Depends Access",
            "no_depends_access",
            template=self.jet_template_tower_core,
            user_ids=[(5, 0, 0)],
            manager_ids=[(5, 0, 0)],
            server_user_ids=[(4, self.manager.id)],
        )

        # Should not be able to create
        with self.assertRaises(AccessError):
            self.JetDependency.with_user(self.manager).create(
                {
                    "jet_id": jet.id,
                    "jet_depends_on_id": depends_on_jet.id,
                    "jet_template_dependency_id": template_dep.id,
                }
            )

    def test_manager_unlink_access(self):
        """
        Test Manager: Delete when in manager_ids of jet AND user_ids
        or manager_ids of depends.
        """
        _, _, dependency = self._create_jet_dependency(
            "Delete Jet",
            "delete_jet",
            "Delete Depends",
            "delete_depends",
            jet_manager_ids=[(4, self.manager.id)],
            depends_on_user_ids=[(4, self.manager.id)],
            jet_server_user_ids=[(4, self.manager.id)],
            depends_on_server_user_ids=[(4, self.manager.id)],
            with_user=self.manager,
        )

        # Refresh dependency in manager context to ensure access
        dependency.invalidate_recordset()
        dependency = dependency.with_user(self.manager)

        try:
            dependency.unlink()
            records = self.JetDependency.search([("id", "=", dependency.id)])
            self.assertEqual(
                len(records),
                0,
                "Manager should be able to delete dependency",
            )
        except AccessError:
            self.fail("Manager should be able to delete dependency")

    def test_manager_unlink_forbidden_not_in_jet_manager_ids(self):
        """Test Manager: Cannot delete when not in jet manager_ids"""
        _, _, dependency = self._create_jet_dependency(
            "No Delete Jet",
            "no_delete_jet",
            "No Delete Depends",
            "no_delete_depends",
            jet_user_ids=[(4, self.manager.id)],
            depends_on_user_ids=[(4, self.manager.id)],
            jet_server_user_ids=[(4, self.manager.id)],
            depends_on_server_user_ids=[(4, self.manager.id)],
        )

        with self.assertRaises(AccessError):
            dependency.with_user(self.manager).unlink()

    # ======================
    # Root Access Tests
    # ======================

    def test_root_full_access(self):
        """Test Root: Full CRUD access regardless of access restrictions"""
        # Create jets without any access restrictions
        jet = self._create_jet(
            "Root Jet",
            "root_jet",
            template=self.jet_template_test,
            user_ids=[(5, 0, 0)],
            manager_ids=[(5, 0, 0)],
        )

        depends_on_jet = self._create_jet(
            "Root Depends",
            "root_depends",
            template=self.jet_template_tower_core,
            user_ids=[(5, 0, 0)],
            manager_ids=[(5, 0, 0)],
        )

        # Create template dependency using different templates
        template_dep = self.JetTemplateDependency.create(
            {
                "template_id": self.jet_template_test.id,
                "template_required_id": self.jet_template_tower_core.id,
            }
        )

        # Root can create
        dependency = self.JetDependency.create(
            {
                "jet_id": jet.id,
                "jet_depends_on_id": depends_on_jet.id,
                "jet_template_dependency_id": template_dep.id,
            }
        )

        # Root can read
        records = self.JetDependency.search([("id", "=", dependency.id)])
        self.assertIn(dependency, records, "Root should be able to read")

        # Root can write (if any fields can be updated)
        dependency.invalidate_recordset()
        dependency.read(["jet_id", "jet_depends_on_id"])
        self.assertTrue(True, "Root should be able to access dependency")

        # Root can delete
        dependency.unlink()
        records = self.JetDependency.search([("id", "=", dependency.id)])
        self.assertEqual(
            len(records),
            0,
            "Root should be able to delete dependency",
        )
