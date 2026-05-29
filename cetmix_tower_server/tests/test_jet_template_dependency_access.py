# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError

from .common_jets import TestTowerJetsCommon


class TestTowerJetTemplateDependencyAccess(TestTowerJetsCommon):
    """
    Test access rules for Jet Template Dependency model
    """

    # ======================
    # Manager Read Access Tests
    # ======================

    def test_manager_read_access_level_manager(self):
        """Test Manager: Read when template access_level is 'Manager' (2)"""
        _, _, dependency = self._create_jet_template_dependency(
            "Manager Level Template", "manager_level_template", access_level="2"
        )

        records = self.JetTemplateDependency.with_user(self.manager).search(
            [("id", "=", dependency.id)]
        )
        self.assertEqual(len(records), 1, "Manager should read when access_level='2'")

    def test_manager_read_access_user_ids(self):
        """Test Manager: Read when added to template user_ids"""
        _, _, dependency = self._create_jet_template_dependency(
            "Manager in Users",
            "manager_in_users",
            access_level="3",
            user_ids=[(4, self.manager.id)],
        )

        records = self.JetTemplateDependency.with_user(self.manager).search(
            [("id", "=", dependency.id)]
        )
        self.assertEqual(len(records), 1, "Manager should read when in user_ids")

    def test_manager_read_access_manager_ids(self):
        """Test Manager: Read when added to template manager_ids"""
        _, _, dependency = self._create_jet_template_dependency(
            "Manager in Managers",
            "manager_in_managers",
            access_level="3",
            manager_ids=[(4, self.manager.id)],
        )

        records = self.JetTemplateDependency.with_user(self.manager).search(
            [("id", "=", dependency.id)]
        )
        self.assertEqual(len(records), 1, "Manager should read when in manager_ids")

    def test_manager_read_no_access_root_level(self):
        """Test Manager: No read access for Root level (3) without user_ids"""
        _, _, dependency = self._create_jet_template_dependency(
            "Root Level Template", "root_level_template", access_level="3"
        )

        records = self.JetTemplateDependency.with_user(self.manager).search(
            [("id", "=", dependency.id)]
        )
        self.assertEqual(len(records), 0, "Manager should not read access_level='3'")

    # ======================
    # Manager CRUD Access Tests
    # ======================

    def test_manager_create_access(self):
        """
        Test Manager: Create when template access_level <= '2'
        AND manager is in template.manager_ids
        """
        # Create a template dependency with manager access using helper
        try:
            _, _, dependency = self._create_jet_template_dependency(
                template_name="Create Manager Template",
                template_reference="create_manager_template",
                access_level="2",
                manager_ids=[(4, self.manager.id)],
                template_required=self.jet_template_tower_core,
                state_required_id=self.state_running.id,
                with_user=self.manager,
            )

            # Ensure dependency was created
            records = self.JetTemplateDependency.search([("id", "=", dependency.id)])
            self.assertIn(
                dependency, records, "Manager should be able to create dependency"
            )
        except AccessError:
            self.fail("Manager should be able to create template dependency")

    def test_manager_create_forbidden_not_in_manager_ids(self):
        """Test Manager: Cannot create when not in template.manager_ids"""
        self.assertRaises(
            AccessError,
            lambda: self.JetTemplateDependency.with_user(self.manager).create(
                {
                    "template_id": self.jet_template_test.id,
                    "template_required_id": self.jet_template_tower_core.id,
                    "state_required_id": self.state_running.id,
                }
            ),
        )

    def test_manager_write_access(self):
        """
        Test Manager: Can write when template access_level <= '2'
        AND manager is in template.manager_ids. Toggle state_required_id.
        """
        # Create dependency with proper access
        _, _, dependency = self._create_jet_template_dependency(
            template_name="Write Manager Template",
            template_reference="write_manager_template",
            access_level="2",
            manager_ids=[(4, self.manager.id)],
            template_required=self.jet_template_tower_core,
            state_required_id=self.state_running.id,
            with_user=self.manager,
        )

        # Perform an actual write: change state_required_id
        try:
            dependency.invalidate_recordset()
            dependency.with_user(self.manager).write(
                {"state_required_id": self.state_stopped.id}
            )
        except AccessError:
            self.fail("Manager should be able to write state_required_id")

    def test_manager_unlink_access(self):
        """
        Test Manager: Can unlink when template access_level <= '2'
        AND manager is in template.manager_ids.
        """
        # Create dependency with proper access
        _, _, dependency = self._create_jet_template_dependency(
            template_name="Unlink Manager Template",
            template_reference="unlink_manager_template",
            access_level="2",
            manager_ids=[(4, self.manager.id)],
            template_required=self.jet_template_tower_core,
            state_required_id=self.state_running.id,
            with_user=self.manager,
        )

        dependency.invalidate_recordset()
        dependency = dependency.with_user(self.manager)
        try:
            dependency.unlink()
            records = self.JetTemplateDependency.search([("id", "=", dependency.id)])
            self.assertEqual(
                len(records), 0, "Manager should be able to unlink dependency"
            )
        except AccessError:
            self.fail("Manager should be able to unlink dependency")

    # ======================
    # Root Access Tests
    # ======================

    def test_root_full_access(self):
        """Root: Full CRUD access regardless of access restrictions"""
        # Root can create
        _, _, dependency = self._create_jet_template_dependency(
            template_name="Root Template",
            template_reference="root_template",
            access_level="3",
            template_required=self.jet_template_tower_core,
            state_required_id=self.state_running.id,
            with_user=self.root,
        )

        # Root can read
        records = self.JetTemplateDependency.with_user(self.root).search(
            [("id", "=", dependency.id)]
        )
        self.assertIn(dependency, records, "Root should be able to read")

        # Root can write allowed field
        dependency.invalidate_recordset()
        dependency.with_user(self.root).write(
            {"state_required_id": self.state_running.id}
        )

        # Root can delete
        dependency.with_user(self.root).unlink()
        records = self.JetTemplateDependency.with_user(self.root).search(
            [("id", "=", dependency.id)]
        )
        self.assertEqual(len(records), 0, "Root should be able to delete dependency")
