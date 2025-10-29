# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from .common_jets import TestTowerJetsCommon


class TestTowerJetTemplateDependencyAccess(TestTowerJetsCommon):
    """
    Test access rules for Jet Template Dependency model
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
