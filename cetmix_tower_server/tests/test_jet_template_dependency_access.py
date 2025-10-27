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

    def _create_dependency(
        self,
        template_name,
        template_reference,
        access_level="2",
        user_ids=None,
        manager_ids=None,
    ):
        """Helper method to create a dependency between two templates"""
        # Create template
        template_vals = {
            "name": template_name,
            "reference": template_reference,
            "access_level": access_level,
            "user_ids": user_ids if user_ids is not None else [(5, 0, 0)],
            "manager_ids": manager_ids if manager_ids is not None else [(5, 0, 0)],
        }
        template = self.JetTemplate.create(template_vals)

        # Create required template
        required_template = self.JetTemplate.create(
            {
                "name": "Required Template",
                "reference": "required_template",
                "access_level": "2",
            }
        )

        # Create dependency
        dependency = self.JetTemplateDependency.create(
            {
                "template_id": template.id,
                "template_required_id": required_template.id,
            }
        )

        return template, required_template, dependency

    # ======================
    # Manager Read Access Tests
    # ======================

    def test_manager_read_access_level_user(self):
        """Test Manager: Read when template access_level is 'User' (1)"""
        _, _, dependency = self._create_dependency(
            "User Level Template", "user_level_template", access_level="1"
        )

        records = self.JetTemplateDependency.with_user(self.manager).search(
            [("id", "=", dependency.id)]
        )
        self.assertEqual(len(records), 1, "Manager should read when access_level='1'")

    def test_manager_read_access_level_manager(self):
        """Test Manager: Read when template access_level is 'Manager' (2)"""
        _, _, dependency = self._create_dependency(
            "Manager Level Template", "manager_level_template", access_level="2"
        )

        records = self.JetTemplateDependency.with_user(self.manager).search(
            [("id", "=", dependency.id)]
        )
        self.assertEqual(len(records), 1, "Manager should read when access_level='2'")

    def test_manager_read_access_user_ids(self):
        """Test Manager: Read when added to template user_ids"""
        _, _, dependency = self._create_dependency(
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
        _, _, dependency = self._create_dependency(
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
        _, _, dependency = self._create_dependency(
            "Root Level Template", "root_level_template", access_level="3"
        )

        records = self.JetTemplateDependency.with_user(self.manager).search(
            [("id", "=", dependency.id)]
        )
        self.assertEqual(len(records), 0, "Manager should not read access_level='3'")
