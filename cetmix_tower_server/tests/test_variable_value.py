from odoo.exceptions import AccessError

from . import common


class TestTowerVariableValue(common.TestTowerCommon):
    """Testing variable values."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create additional test users
        cls.user2 = cls.Users.create(
            {
                "name": "Test User 2",
                "login": "test_user2",
                "email": "test_user2@example.com",
                "groups_id": [(6, 0, [cls.group_user.id])],
            }
        )

        cls.manager2 = cls.Users.create(
            {
                "name": "Test Manager 2",
                "login": "test_manager2",
                "email": "test_manager2@example.com",
                "groups_id": [(6, 0, [cls.group_manager.id])],
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

        # Create servers
        cls.server_1 = cls.Server.create(
            {
                "name": "Test Server 1",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "os_id": cls.os_debian_10.id,
                "user_ids": [(4, cls.user.id)],
                "manager_ids": [(4, cls.manager.id)],
            }
        )

        cls.server_2 = cls.Server.create(
            {
                "name": "Test Server 2",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "os_id": cls.os_debian_10.id,
                "user_ids": [(4, cls.user2.id)],
                "manager_ids": [(4, cls.manager2.id)],
            }
        )

        # Create test command
        cls.test_command = cls.Command.create(
            {
                "name": "Test Command",
                "code": "echo 'test'",
            }
        )

        # Create flight plan and its components
        cls.test_plan = cls.Plan.create(
            {
                "name": "Test Plan",
                "user_ids": [(4, cls.user.id)],
                "manager_ids": [(4, cls.manager.id)],
            }
        )

        cls.test_plan_line = cls.plan_line.create(
            {
                "name": "Test Line",
                "plan_id": cls.test_plan.id,
                "command_id": cls.test_command.id,
            }
        )

        cls.test_plan_line_action = cls.plan_line_action.create(
            {
                "name": "Test Action",
                "line_id": cls.test_plan_line.id,
                "condition": "==",
                "value_char": "0",
                "action": "n",
            }
        )

        # Create variable values
        cls.global_value_1 = cls.VariableValue.create(
            {
                "variable_id": cls.variable_level_1.id,
                "value_char": "global_value_1",
            }
        )

        cls.global_value_2 = cls.VariableValue.create(
            {
                "variable_id": cls.variable_level_2.id,
                "value_char": "global_value_2",
            }
        )

        cls.server_value_1 = cls.VariableValue.create(
            {
                "variable_id": cls.variable_level_1.id,
                "value_char": "server_value_1",
                "server_id": cls.server_1.id,
            }
        )

        cls.server_value_2 = cls.VariableValue.with_user(cls.manager).create(
            {
                "variable_id": cls.variable_level_2.id,
                "value_char": "server_value_2",
                "server_id": cls.server_1.id,
            }
        )

        cls.plan_value_1 = cls.VariableValue.create(
            {
                "variable_id": cls.variable_level_1.id,
                "value_char": "plan_value_1",
                "plan_line_action_id": cls.test_plan_line_action.id,
            }
        )

        cls.plan_value_2 = cls.VariableValue.create(
            {
                "variable_id": cls.variable_level_2.id,
                "value_char": "plan_value_2",
                "plan_line_action_id": cls.test_plan_line_action.id,
            }
        )

        # Add server template setup
        cls.server_template = cls.ServerTemplate.create(
            {
                "name": "Test Template",
                "ssh_username": "admin",
                "ssh_password": "password",
                "os_id": cls.os_debian_10.id,
                "manager_ids": [
                    (4, cls.manager.id)
                ],  # Only managers should have access
            }
        )

        # Add template variable values
        cls.template_value_1 = cls.VariableValue.create(
            {
                "variable_id": cls.variable_level_1.id,
                "value_char": "template_value_1",
                "server_template_id": cls.server_template.id,
            }
        )

        cls.template_value_2 = cls.VariableValue.with_user(cls.manager).create(
            {
                "variable_id": cls.variable_level_2.id,
                "value_char": "template_value_2",
                "server_template_id": cls.server_template.id,
            }
        )

        # Add server to plan
        cls.test_plan.write({"server_ids": [(4, cls.server_1.id)]})

    def test_variable_value_access_rights(self):
        """
        Test access rights for variable values
        based on access levels and user roles.
        """

        # Test User Access
        # ---------------
        user_values = self.VariableValue.with_user(self.user).search(
            [
                (
                    "id",
                    "in",
                    [
                        self.global_value_1.id,
                        self.global_value_2.id,
                        self.server_value_1.id,
                        self.server_value_2.id,
                        self.plan_value_1.id,
                        self.plan_value_2.id,
                    ],
                )
            ]
        )

        # User should see level 1 global values and level 1 values
        #  from their server/plan
        self.assertEqual(len(user_values), 3)
        self.assertIn(self.global_value_1.id, user_values.ids)
        self.assertIn(self.server_value_1.id, user_values.ids)
        self.assertIn(self.plan_value_1.id, user_values.ids)

        # User should not be able to create/write/unlink values
        with self.assertRaises(AccessError):
            self.VariableValue.with_user(self.user).create(
                {
                    "variable_id": self.variable_level_1.id,
                    "value_char": "test",
                    "server_id": self.server_1.id,
                }
            )

        with self.assertRaises(AccessError):
            self.server_value_1.with_user(self.user).write({"value_char": "new_value"})

        with self.assertRaises(AccessError):
            self.server_value_1.with_user(self.user).unlink()

        # Test Manager Access
        # ------------------
        manager_values = self.VariableValue.with_user(self.manager).search(
            [
                (
                    "id",
                    "in",
                    [
                        self.global_value_1.id,
                        self.global_value_2.id,
                        self.server_value_1.id,
                        self.server_value_2.id,
                        self.plan_value_1.id,
                        self.plan_value_2.id,
                    ],
                )
            ]
        )

        # Manager should see all level 1 and 2 values from their server/plan
        self.assertEqual(len(manager_values), 6)

        # Manager should be able to create values for their server/plan
        test_variable = self.Variable.create(
            {
                "name": "Test Variable",
                "access_level": "2",
            }
        )
        try:
            new_value = self.VariableValue.with_user(self.manager).create(
                {
                    "variable_id": test_variable.id,
                    "value_char": "manager_value",
                    "server_id": self.server_1.id,
                }
            )
        except AccessError:
            self.fail("Manager should be able to create values for their server")

        # Manager should be able to modify values for their server/plan
        try:
            self.server_value_2.with_user(self.manager).write(
                {"value_char": "updated_value"}
            )
        except AccessError:
            self.fail("Manager should be able to modify values for their server")

        # Manager should be able to delete their own values
        try:
            new_value.with_user(self.manager).unlink()
        except AccessError:
            self.fail("Manager should be able to delete their own values")

        # Manager should not be able to modify other manager's values
        with self.assertRaises(AccessError):
            self.VariableValue.with_user(self.manager).create(
                {
                    "variable_id": self.variable_level_1.id,
                    "value_char": "test",
                    "server_id": self.server_2.id,
                }
            )

        # Test Root Access
        # ---------------
        root_values = self.VariableValue.with_user(self.root).search(
            [
                (
                    "id",
                    "in",
                    [
                        self.global_value_1.id,
                        self.global_value_2.id,
                        self.server_value_1.id,
                        self.server_value_2.id,
                        self.plan_value_1.id,
                        self.plan_value_2.id,
                    ],
                )
            ]
        )

        # Root should see all values
        self.assertEqual(len(root_values), 6)

        # Root should be able to create any value
        try:
            root_value = self.VariableValue.with_user(self.root).create(
                {
                    "variable_id": self.variable_level_2.id,
                    "value_char": "root_value",
                    "server_id": self.server_2.id,
                    "access_level": "2",
                }
            )
        except AccessError:
            self.fail("Root should be able to create any value")

        # Root should be able to modify any value
        try:
            self.server_value_2.with_user(self.root).write(
                {"value_char": "root_updated"}
            )
        except AccessError:
            self.fail("Root should be able to modify any value")

        # Root should be able to delete any value
        try:
            root_value.with_user(self.root).unlink()
        except AccessError:
            self.fail("Root should be able to delete any value")

    def test_server_template_access(self):
        """Test access rights for server template variable values"""

        # Test user access to template values
        # (should see none since they don't have template access)
        user_template_values = self.VariableValue.with_user(self.user).search(
            [("server_template_id", "=", self.server_template.id)]
        )
        self.assertEqual(
            len(user_template_values), 0
        )  # Users can't see template values

        # Test manager access to template values
        manager_template_values = self.VariableValue.with_user(self.manager).search(
            [("server_template_id", "=", self.server_template.id)]
        )
        self.assertEqual(len(manager_template_values), 2)

        # Create a new variable for testing manager create rights
        test_variable = self.Variable.create(
            {
                "name": "Test Template Manager Variable",
                "access_level": "2",
            }
        )

        # Test manager create rights
        new_template_value = self.VariableValue.with_user(self.manager).create(
            {
                "variable_id": test_variable.id,  # Use the new variable
                "value_char": "new_template_value",
                "server_template_id": self.server_template.id,
            }
        )
        self.assertTrue(new_template_value.exists())

        # Test manager write rights
        self.template_value_2.with_user(self.manager).write(
            {"value_char": "updated_template_value"}
        )
        self.assertEqual(self.template_value_2.value_char, "updated_template_value")

        # Test manager unlink rights (only own records)
        new_template_value.with_user(self.manager).unlink()
        self.assertFalse(new_template_value.exists())

    def test_server_template_manager_in_users_access(self):
        """Test access rights for server template when manager is in user_ids only"""

        # Create new template with manager in user_ids only (not in manager_ids)
        template_with_manager_user = self.ServerTemplate.create(
            {
                "name": "Template With Manager User",
                "ssh_username": "admin",
                "ssh_password": "password",
                "os_id": self.os_debian_10.id,
                "user_ids": [(4, self.manager.id)],  # Add manager to user_ids only
            }
        )

        # Create test value as root to set up the test
        template_value_1 = self.VariableValue.create(
            {
                "variable_id": self.variable_level_1.id,
                "value_char": "manager_user_value_1",
                "server_template_id": template_with_manager_user.id,
            }
        )

        # Test manager can only read level 1 values (like a regular user)
        manager_values = self.VariableValue.with_user(self.manager).search(
            [("server_template_id", "=", template_with_manager_user.id)]
        )
        self.assertEqual(len(manager_values), 1)
        self.assertIn(template_value_1.id, manager_values.ids)

        # Create a new variable for testing create access
        test_variable = self.Variable.create(
            {
                "name": "Test Template User Variable",
                "access_level": "1",
            }
        )

        # Test manager cannot create values
        with self.assertRaises(AccessError):
            self.VariableValue.with_user(self.manager).create(
                {
                    "variable_id": test_variable.id,  # Use the new variable
                    "value_char": "new_manager_user_value",
                    "server_template_id": template_with_manager_user.id,
                }
            )

        # Test manager cannot write values
        with self.assertRaises(AccessError):
            template_value_1.with_user(self.manager).write(
                {"value_char": "updated_manager_user_value"}
            )

        # Test manager cannot delete values
        with self.assertRaises(AccessError):
            template_value_1.with_user(self.manager).unlink()

    def test_plan_server_access(self):
        """Test access rights for plan server variable values"""

        # Create a new variable for testing
        test_variable = self.Variable.create(
            {
                "name": "Test Plan Server Variable",
                "access_level": "2",
            }
        )

        # Create variable value for plan server (only assign to server)
        plan_server_value = self.VariableValue.with_user(self.manager).create(
            {
                "variable_id": test_variable.id,
                "value_char": "plan_server_value",
                "server_id": self.server_1.id,
            }
        )

        # Test user read access
        user_plan_server_values = self.VariableValue.with_user(self.user).search(
            [("server_id", "=", self.server_1.id), ("access_level", "=", "1")]
        )
        self.assertTrue(user_plan_server_values)

        # Test manager read/write access
        manager_plan_server_values = self.VariableValue.with_user(self.manager).search(
            [("server_id", "=", self.server_1.id)]
        )
        self.assertTrue(manager_plan_server_values)

        # Test manager write rights
        plan_server_value.with_user(self.manager).write(
            {"value_char": "updated_plan_server_value"}
        )
        self.assertEqual(plan_server_value.value_char, "updated_plan_server_value")

        # Create another new variable for testing create rights
        test_variable_2 = self.Variable.create(
            {
                "name": "Test Plan Server Variable 2",
                "access_level": "2",
            }
        )

        # Test manager create rights (only assign to server)
        new_plan_server_value = self.VariableValue.with_user(self.manager).create(
            {
                "variable_id": test_variable_2.id,
                "value_char": "new_plan_server_value",
                "server_id": self.server_1.id,
            }
        )
        self.assertTrue(new_plan_server_value.exists())

        # Test manager unlink rights (only own records)
        new_plan_server_value.with_user(self.manager).unlink()
        self.assertFalse(new_plan_server_value.exists())

        # Test plan-specific variable values
        test_variable_3 = self.Variable.create(
            {
                "name": "Test Plan Action Variable",
                "access_level": "2",
            }
        )

        # Create variable value for plan action
        plan_action_value = self.VariableValue.with_user(self.manager).create(
            {
                "variable_id": test_variable_3.id,
                "value_char": "plan_action_value",
                "plan_line_action_id": self.test_plan_line_action.id,
            }
        )
        self.assertTrue(plan_action_value.exists())

        # Test manager access to plan action values
        manager_plan_values = self.VariableValue.with_user(self.manager).search(
            [("plan_line_action_id", "=", self.test_plan_line_action.id)]
        )
        self.assertIn(plan_action_value.id, manager_plan_values.ids)

    def test_reference_pattern_global_server_template_action(self):
        """Ensure model-scoped references follow the required pattern."""
        # Global
        model_ref = self.VariableValue._get_model_generic_reference()
        self.assertTrue(self.global_value_1.reference.endswith(f"_{model_ref}_global"))

        # Server
        srv_model_ref = self.Server._get_model_generic_reference()
        self.assertTrue(
            self.server_value_1.reference.startswith(
                f"{self.variable_level_1.reference}_{model_ref}_{srv_model_ref}_"
            )
        )

        # Server Template
        tmpl_model_ref = self.ServerTemplate._get_model_generic_reference()
        self.assertTrue(
            self.template_value_1.reference.startswith(
                f"{self.variable_level_1.reference}_{model_ref}_{tmpl_model_ref}_"
            )
        )

        # Plan Line Action
        action_model_ref = self.plan_line_action._get_model_generic_reference()
        self.assertTrue(
            self.plan_value_1.reference.startswith(
                f"{self.variable_level_1.reference}_{model_ref}_{action_model_ref}_"
            )
        )
