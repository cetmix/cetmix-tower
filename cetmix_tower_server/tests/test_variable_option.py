from odoo.exceptions import AccessError, ValidationError

from .common import TestTowerCommon


class TestTowerVariableOption(TestTowerCommon):
    """Test case class to validate the behavior of
    'cx.tower.variable.option' model.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.variable_odoo_versions = cls.Variable.create(
            {
                "name": "odoo_versions",
                "variable_type": "o",
            }
        )

        cls.variable_option_17_0 = cls.VariableOption.create(
            {
                "name": "17.0",
                "value_char": "17.0",
                "variable_id": cls.variable_odoo_versions.id,
            }
        )

        cls.variable_option_18_0 = cls.VariableOption.create(
            {
                "name": "18.0",
                "value_char": "18.0",
                "variable_id": cls.variable_odoo_versions.id,
            }
        )

        # Create additional test users
        cls.manager2 = cls.Users.create(
            {
                "name": "Manager 2",
                "login": "manager2@example.com",
                "groups_id": [(4, cls.group_manager.id)],
            }
        )

        # Create variables with different access levels
        cls.variable_level_1 = cls.Variable.create(
            {
                "name": "Level 1 Variable",
                "access_level": "1",
            }
        )

        cls.variable_level_2 = cls.Variable.create(
            {
                "name": "Level 2 Variable",
                "access_level": "2",
            }
        )

        # Create options with different access levels (inherited from variables)
        cls.option_level_1 = cls.VariableOption.create(
            {
                "name": "Option Level 1",
                "value_char": "value1",
                "variable_id": cls.variable_level_1.id,
            }
        )

        cls.option_level_2 = cls.VariableOption.create(
            {
                "name": "Option Level 2",
                "value_char": "value2",
                "variable_id": cls.variable_level_2.id,
            }
        )

    def test_variable_value_set_from_option(self):
        """Test that a variable value can be set from an option."""

        variable_value = self.VariableValue.create(
            {
                "server_id": self.server_test_1.id,
                "variable_id": self.variable_odoo_versions.id,
            }
        )

        # -- 1 --
        # Set value_char to an existing option
        variable_value.value_char = "17.0"
        self.assertEqual(
            variable_value.option_id,
            self.variable_option_17_0,
        )

        # -- 2 --
        # Set value_char to a non-existing option
        variable_meme_level = self.Variable.create(
            {
                "name": "meme_level",
                "variable_type": "o",
            }
        )
        option_meme_level_high = self.VariableOption.create(
            {
                "name": "high",
                "value_char": "high",
                "variable_id": variable_meme_level.id,
            }
        )
        with self.assertRaises(ValidationError):
            variable_value.option_id = option_meme_level_high

        # -- 3 --
        # Set value_char to a non-existing option
        variable_value.value_char = "29.0"
        self.assertFalse(variable_value.option_id)

    def test_access_level_consistency(self):
        """Test that variable option access level cannot be lower
        than variable access level."""

        # Create a variable with access level "2"
        variable_restricted = self.Variable.create(
            {
                "name": "restricted_variable",
                "variable_type": "o",
                "access_level": "2",
            }
        )

        # Should succeed: option with same access level as variable
        try:
            self.VariableOption.create(
                {
                    "name": "Option 1",
                    "value_char": "value1",
                    "variable_id": variable_restricted.id,
                    "access_level": "2",
                }
            )
        except ValidationError:
            self.fail("Should allow creating option with same access level as variable")

        # Should succeed: option with higher access level than variable
        try:
            self.VariableOption.create(
                {
                    "name": "Option 2",
                    "value_char": "value2",
                    "variable_id": variable_restricted.id,
                    "access_level": "3",
                }
            )
        except ValidationError:
            self.fail(
                "Should allow creating option with higher access level than variable"
            )

        # Should fail: option with lower access level than variable
        with self.assertRaises(
            ValidationError,
            msg="Should not allow creating option "
            "with lower access level than variable",
        ):
            self.VariableOption.create(
                {
                    "name": "Option 3",
                    "value_char": "value3",
                    "variable_id": variable_restricted.id,
                    "access_level": "1",
                }
            )

        # Test updating existing option's access level
        option = self.VariableOption.create(
            {
                "name": "Option 4",
                "value_char": "value4",
                "variable_id": variable_restricted.id,
                "access_level": "2",
            }
        )

        # Should fail: updating to lower access level than variable
        with self.assertRaises(
            ValidationError,
            msg="Should not allow updating option to lower access level than variable",
        ):
            option.write({"access_level": "1"})

        # Should succeed: updating to higher access level than variable
        try:
            option.write({"access_level": "3"})
        except ValidationError:
            self.fail(
                "Should allow updating option to higher access level than variable"
            )

    def test_variable_option_access_rights(self):
        """
        Test access rights for variable options
        based on access levels and user roles.
        """

        # Test User Access
        # ---------------
        # Should see level 1 options only
        records = self.VariableOption.with_user(self.user).search(
            [("id", "in", [self.option_level_1.id, self.option_level_2.id])]
        )
        self.assertEqual(len(records), 1, "User should only see level 1 options")
        self.assertEqual(
            records.id, self.option_level_1.id, "User should only see level 1 options"
        )

        # Test Manager Access
        # -----------------
        # Should see level 1 and 2 options
        records = self.VariableOption.with_user(self.manager).search(
            [("id", "in", [self.option_level_1.id, self.option_level_2.id])]
        )
        self.assertEqual(len(records), 2, "Manager should see level 1 and 2 options")
        self.assertIn(
            self.option_level_1.id, records.ids, "Manager should see level 1 options"
        )
        self.assertIn(
            self.option_level_2.id, records.ids, "Manager should see level 2 options"
        )

        # Test Manager Write Access
        # -----------------------
        # Create an option as manager
        manager_option = self.VariableOption.with_user(self.manager).create(
            {
                "name": "Manager Created Option",
                "value_char": "manager_value",
                "variable_id": self.variable_level_2.id,
            }
        )

        # Manager should be able to modify their own option
        try:
            manager_option.with_user(self.manager).write({"name": "Updated Name"})
        except AccessError:
            self.fail("Manager should be able to modify their own options")

        # Manager should not be able to modify another manager's option
        manager2_option = self.VariableOption.with_user(self.manager2).create(
            {
                "name": "Other Manager Option",
                "value_char": "other_value",
                "variable_id": self.variable_level_2.id,
            }
        )

        with self.assertRaises(AccessError):
            manager2_option.with_user(self.manager).write({"name": "Try Update"})

        # Test Root Access
        # --------------
        # Root should see all options
        records = self.VariableOption.with_user(self.root).search(
            [("id", "in", [self.option_level_1.id, self.option_level_2.id])]
        )
        self.assertEqual(len(records), 2, "Root should see all options")

        # Root should be able to create any option
        try:
            self.VariableOption.with_user(self.root).create(
                {
                    "name": "Root Created Option",
                    "value_char": "root_value",
                    "variable_id": self.variable_level_2.id,
                }
            )
        except AccessError:
            self.fail("Root should be able to create any option")

        # Root should be able to modify any option
        try:
            self.option_level_2.with_user(self.root).write({"name": "Updated by Root"})
        except AccessError:
            self.fail("Root should be able to modify any option")
