from odoo.exceptions import AccessError, ValidationError

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

        # Create Jet Template
        cls.jet_template = cls.JetTemplate.create(
            {
                "name": "Test Jet Template",
                "server_ids": [(4, cls.server_1.id)],
                "user_ids": [(4, cls.user.id)],
                "manager_ids": [(4, cls.manager.id)],
            }
        )

        # Create Jet Template variable values
        cls.jet_template_value_1 = cls.VariableValue.create(
            {
                "variable_id": cls.variable_level_1.id,
                "value_char": "jet_template_value_1",
                "jet_template_id": cls.jet_template.id,
            }
        )

        cls.jet_template_value_2 = cls.VariableValue.with_user(cls.manager).create(
            {
                "variable_id": cls.variable_level_2.id,
                "value_char": "jet_template_value_2",
                "jet_template_id": cls.jet_template.id,
            }
        )

        # Create Jet
        cls.jet = cls.Jet.create(
            {
                "name": "Test Jet",
                "jet_template_id": cls.jet_template.id,
                "server_id": cls.server_1.id,
                "user_ids": [(4, cls.user.id)],
                "manager_ids": [(4, cls.manager.id)],
            }
        )

        # Create Jet variable values
        cls.jet_value_1 = cls.VariableValue.create(
            {
                "variable_id": cls.variable_level_1.id,
                "value_char": "jet_value_1",
                "jet_id": cls.jet.id,
            }
        )

        cls.jet_value_2 = cls.VariableValue.with_user(cls.manager).create(
            {
                "variable_id": cls.variable_level_2.id,
                "value_char": "jet_value_2",
                "jet_id": cls.jet.id,
            }
        )

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

        # Create test values as root to set up the test
        template_value_1 = self.VariableValue.create(
            {
                "variable_id": self.variable_level_1.id,
                "value_char": "manager_user_value_1",
                "server_template_id": template_with_manager_user.id,
            }
        )

        template_value_2 = self.VariableValue.create(
            {
                "variable_id": self.variable_level_2.id,
                "value_char": "manager_user_value_2",
                "server_template_id": template_with_manager_user.id,
            }
        )

        # Test manager can read both level 1 and level 2 values
        # (Manager Read rule allows access_level <= '2' when manager is in user_ids)
        manager_values = self.VariableValue.with_user(self.manager).search(
            [("server_template_id", "=", template_with_manager_user.id)]
        )
        self.assertEqual(len(manager_values), 2)
        self.assertIn(template_value_1.id, manager_values.ids)
        self.assertIn(template_value_2.id, manager_values.ids)

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

    def test_jet_access(self):
        """Test access rights for Jet variable values"""

        # Test user access to jet values
        # User should see level 1 values from jets they're added to
        user_jet_values = self.VariableValue.with_user(self.user).search(
            [("jet_id", "=", self.jet.id)]
        )
        self.assertEqual(len(user_jet_values), 1)
        self.assertIn(self.jet_value_1.id, user_jet_values.ids)

        # User should not be able to create/write/unlink values
        with self.assertRaises(AccessError):
            self.VariableValue.with_user(self.user).create(
                {
                    "variable_id": self.variable_level_1.id,
                    "value_char": "test",
                    "jet_id": self.jet.id,
                }
            )

        with self.assertRaises(AccessError):
            self.jet_value_1.with_user(self.user).write({"value_char": "new_value"})

        with self.assertRaises(AccessError):
            self.jet_value_1.with_user(self.user).unlink()

        # Test manager access to jet values
        # Manager should see all level 1 and 2 values from jets they're added to
        manager_jet_values = self.VariableValue.with_user(self.manager).search(
            [("jet_id", "=", self.jet.id)]
        )
        self.assertEqual(len(manager_jet_values), 2)
        self.assertIn(self.jet_value_1.id, manager_jet_values.ids)
        self.assertIn(self.jet_value_2.id, manager_jet_values.ids)

        # Create a new variable for testing manager create rights
        test_variable = self.Variable.create(
            {
                "name": "Test Jet Manager Variable",
                "access_level": "2",
            }
        )

        # Test manager create rights (only when manager in jet manager_ids)
        new_jet_value = self.VariableValue.with_user(self.manager).create(
            {
                "variable_id": test_variable.id,
                "value_char": "new_jet_value",
                "jet_id": self.jet.id,
            }
        )
        self.assertTrue(new_jet_value.exists())

        # Test manager write rights
        self.jet_value_2.with_user(self.manager).write(
            {"value_char": "updated_jet_value"}
        )
        self.assertEqual(self.jet_value_2.value_char, "updated_jet_value")

        # Test manager unlink rights (only own records)
        new_jet_value.with_user(self.manager).unlink()
        self.assertFalse(new_jet_value.exists())

        # Test manager cannot create values for jets they're not managers of
        jet_without_manager = self.Jet.create(
            {
                "name": "Jet Without Manager",
                "jet_template_id": self.jet_template.id,
                "server_id": self.server_1.id,
                "user_ids": [(4, self.user2.id)],
                "manager_ids": [(4, self.manager2.id)],
            }
        )

        with self.assertRaises(AccessError):
            self.VariableValue.with_user(self.manager).create(
                {
                    "variable_id": self.variable_level_1.id,
                    "value_char": "test",
                    "jet_id": jet_without_manager.id,
                }
            )

    def test_jet_manager_in_users_access(self):
        """Test access rights for Jet when manager is in user_ids only"""

        # Create new jet with manager in user_ids only (not in manager_ids)
        jet_with_manager_user = self.Jet.create(
            {
                "name": "Jet With Manager User",
                "jet_template_id": self.jet_template.id,
                "server_id": self.server_1.id,
                "user_ids": [(4, self.manager.id)],  # Add manager to user_ids only
                "manager_ids": [(5, 0, 0)],
            }
        )

        # Create test values as root to set up the test
        jet_value_1 = self.VariableValue.create(
            {
                "variable_id": self.variable_level_1.id,
                "value_char": "manager_user_value_1",
                "jet_id": jet_with_manager_user.id,
            }
        )

        jet_value_2 = self.VariableValue.create(
            {
                "variable_id": self.variable_level_2.id,
                "value_char": "manager_user_value_2",
                "jet_id": jet_with_manager_user.id,
            }
        )

        # Test manager can read both level 1 and level 2 values
        # (Manager Read rule allows access_level <= '2' when manager is in user_ids)
        manager_values = self.VariableValue.with_user(self.manager).search(
            [("jet_id", "=", jet_with_manager_user.id)]
        )
        self.assertEqual(len(manager_values), 2)
        self.assertIn(jet_value_1.id, manager_values.ids)
        self.assertIn(jet_value_2.id, manager_values.ids)

        # Create a new variable for testing create access
        test_variable = self.Variable.create(
            {
                "name": "Test Jet User Variable",
                "access_level": "1",
            }
        )

        # Test manager cannot create values
        with self.assertRaises(AccessError):
            self.VariableValue.with_user(self.manager).create(
                {
                    "variable_id": test_variable.id,
                    "value_char": "new_manager_user_value",
                    "jet_id": jet_with_manager_user.id,
                }
            )

        # Test manager cannot write values
        with self.assertRaises(AccessError):
            jet_value_1.with_user(self.manager).write(
                {"value_char": "updated_manager_user_value"}
            )

        # Test manager cannot delete values
        with self.assertRaises(AccessError):
            jet_value_1.with_user(self.manager).unlink()

    def test_jet_template_access(self):
        """Test access rights for Jet Template variable values"""

        # Test user access to template values
        # User should see level 1 values from jet templates they're added to
        user_jet_template_values = self.VariableValue.with_user(self.user).search(
            [("jet_template_id", "=", self.jet_template.id)]
        )
        self.assertEqual(len(user_jet_template_values), 1)
        self.assertIn(self.jet_template_value_1.id, user_jet_template_values.ids)

        # User should not be able to create/write/unlink values
        with self.assertRaises(AccessError):
            self.VariableValue.with_user(self.user).create(
                {
                    "variable_id": self.variable_level_1.id,
                    "value_char": "test",
                    "jet_template_id": self.jet_template.id,
                }
            )

        with self.assertRaises(AccessError):
            self.jet_template_value_1.with_user(self.user).write(
                {"value_char": "new_value"}
            )

        with self.assertRaises(AccessError):
            self.jet_template_value_1.with_user(self.user).unlink()

        # Test manager access to template values
        # Manager should see all level 1 and 2 values from jet templates
        # they're added to
        manager_jet_template_values = self.VariableValue.with_user(self.manager).search(
            [("jet_template_id", "=", self.jet_template.id)]
        )
        self.assertEqual(len(manager_jet_template_values), 2)
        self.assertIn(self.jet_template_value_1.id, manager_jet_template_values.ids)
        self.assertIn(self.jet_template_value_2.id, manager_jet_template_values.ids)

        # Create a new variable for testing manager create rights
        test_variable = self.Variable.create(
            {
                "name": "Test Jet Template Manager Variable",
                "access_level": "2",
            }
        )

        # Test manager create rights (only when manager in template manager_ids)
        new_jet_template_value = self.VariableValue.with_user(self.manager).create(
            {
                "variable_id": test_variable.id,
                "value_char": "new_jet_template_value",
                "jet_template_id": self.jet_template.id,
            }
        )
        self.assertTrue(new_jet_template_value.exists())

        # Test manager write rights
        self.jet_template_value_2.with_user(self.manager).write(
            {"value_char": "updated_jet_template_value"}
        )
        self.assertEqual(
            self.jet_template_value_2.value_char, "updated_jet_template_value"
        )

        # Test manager unlink rights (only own records)
        new_jet_template_value.with_user(self.manager).unlink()
        self.assertFalse(new_jet_template_value.exists())

        # Test manager cannot create values for templates they're not managers of
        jet_template_without_manager = self.JetTemplate.create(
            {
                "name": "Template Without Manager",
                "server_ids": [(4, self.server_1.id)],
                "user_ids": [(4, self.user2.id)],
                "manager_ids": [(4, self.manager2.id)],
            }
        )

        with self.assertRaises(AccessError):
            self.VariableValue.with_user(self.manager).create(
                {
                    "variable_id": self.variable_level_1.id,
                    "value_char": "test",
                    "jet_template_id": jet_template_without_manager.id,
                }
            )

    def test_jet_template_manager_in_users_access(self):
        """Test access rights for Jet Template when manager is in user_ids only"""

        # Create new template with manager in user_ids only (not in manager_ids)
        template_with_manager_user = self.JetTemplate.create(
            {
                "name": "Template With Manager User",
                "server_ids": [(4, self.server_1.id)],
                "user_ids": [(4, self.manager.id)],  # Add manager to user_ids only
                "manager_ids": [(5, 0, 0)],
            }
        )

        # Create test values as root to set up the test
        template_value_1 = self.VariableValue.create(
            {
                "variable_id": self.variable_level_1.id,
                "value_char": "manager_user_value_1",
                "jet_template_id": template_with_manager_user.id,
            }
        )

        template_value_2 = self.VariableValue.create(
            {
                "variable_id": self.variable_level_2.id,
                "value_char": "manager_user_value_2",
                "jet_template_id": template_with_manager_user.id,
            }
        )

        # Test manager can read both level 1 and level 2 values
        # (Manager Read rule allows access_level <= '2' when manager is in user_ids)
        manager_values = self.VariableValue.with_user(self.manager).search(
            [("jet_template_id", "=", template_with_manager_user.id)]
        )
        self.assertEqual(len(manager_values), 2)
        self.assertIn(template_value_1.id, manager_values.ids)
        self.assertIn(template_value_2.id, manager_values.ids)

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
                    "variable_id": test_variable.id,
                    "value_char": "new_manager_user_value",
                    "jet_template_id": template_with_manager_user.id,
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

        # Jet Template
        jet_tmpl_model_ref = self.JetTemplate._get_model_generic_reference()
        self.assertTrue(
            self.jet_template_value_1.reference.startswith(
                f"{self.variable_level_1.reference}_{model_ref}_{jet_tmpl_model_ref}_"
            )
        )

        # Jet
        jet_model_ref = self.Jet._get_model_generic_reference()
        self.assertTrue(
            self.jet_value_1.reference.startswith(
                f"{self.variable_level_1.reference}_{model_ref}_{jet_model_ref}_"
            )
        )


class TestVariableValueEnvironment(common.TestTowerCommon):
    """Environments on variable values: assignment and disjoint rule"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.variable_workers = cls.Variable.create({"name": "test_odoo_workers"})
        cls.variable_other = cls.Variable.create({"name": "test_other_variable"})

    def _create_value(self, value_char, environments=None, variable=None, **links):
        """Create a variable value.

        Args:
            value_char (str): value
            environments (cx.tower.environment()): environments of the value
            variable (cx.tower.variable()): variable, workers by default
            **links: m2o fields, eg server_id=1

        Returns:
            cx.tower.variable.value(): created value
        """
        vals = {
            "variable_id": (variable or self.variable_workers).id,
            "value_char": value_char,
        }
        if environments:
            vals["environment_ids"] = [(6, 0, environments.ids)]
        vals.update(links)
        return self.VariableValue.create(vals)

    def _create_server(self):
        """Create a server without variable values"""
        return self.Server.create(
            {
                "name": "Test Environment Server",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "host_key": "test_key",
                "os_id": self.os_debian_10.id,
            }
        )

    def _check_scope(self, **links):
        """Check the disjoint rule in a scope

        Args:
            **links: m2o fields of the scope, nothing for global values
        """
        untagged = self._create_value("2", **links)
        prod = self._create_value("8", self.env_prod, **links)
        # Disjoint environments are allowed
        stage_dev = self._create_value("4", self.env_stage | self.env_dev, **links)
        self.assertEqual(len(untagged | prod | stage_dev), 3)

        # A second untagged value is rejected
        with self.assertRaises(ValidationError):
            self._create_value("3", **links)

        # The same environment twice is rejected
        with self.assertRaises(ValidationError):
            self._create_value("9", self.env_dev, **links)

        # Adding a used environment to an existing value is rejected
        with self.assertRaises(ValidationError):
            prod.environment_ids = [(4, self.env_stage.id)]

        # Removing the environments of a tagged value is rejected,
        # because it would be a second untagged value
        with self.assertRaises(ValidationError):
            prod.environment_ids = [(5, 0, 0)]

    def _check_unarchive(self, **links):
        """Unarchiving a value is checked against the active values

        Args:
            **links: m2o fields of the scope, nothing for global values
        """
        untagged = self._create_value("2", **links)
        prod = self._create_value("8", self.env_prod, **links)
        (untagged | prod).active = False

        # Archived values don't block their replacements
        self._create_value("3", **links)
        self._create_value("9", self.env_prod, **links)

        # Unarchiving would make duplicates
        with self.assertRaises(ValidationError):
            untagged.active = True
        with self.assertRaises(ValidationError):
            prod.action_unarchive()

    def test_unarchive_ignores_archived_siblings(self):
        """Archived values don't block unarchiving,
        even with active_test=False in the context
        """
        links = {"server_id": self.server_test_1.id}
        value_a = self._create_value("2", **links)
        value_a.active = False
        value_b = self._create_value("3", **links)
        value_b.active = False
        value_a.with_context(active_test=False).action_unarchive()
        self.assertTrue(value_a.active)
        self.assertFalse(value_b.active)

    def test_unarchive_server(self):
        """Server: unarchiving can't create a duplicate"""
        self._check_unarchive(server_id=self.server_test_1.id)

    def test_unarchive_jet_template(self):
        """Jet Template: unarchiving can't create a duplicate"""
        self._check_unarchive(jet_template_id=self.jet_template_sample.id)

    def test_unarchive_global(self):
        """Global: unarchiving can't create a duplicate"""
        self._check_unarchive()

    def test_disjoint_server(self):
        """Server values of the same variable have disjoint environments"""
        self._check_scope(server_id=self.server_test_1.id)

        # Another server is another scope
        self._create_value("2", server_id=self._create_server().id)

    def test_disjoint_jet_template(self):
        """Jet Template values of the same variable have disjoint environments"""
        self._check_scope(jet_template_id=self.jet_template_sample.id)

    def test_disjoint_global(self):
        """Global values of the same variable have disjoint environments"""
        self._check_scope()

        # Keep the message checked by `test_variable_value_toggle_global`
        with self.assertRaises(ValidationError) as err:
            self._create_value("5")
        self.assertEqual(
            err.exception.args[0],
            "Only one global value can be defined for variable "
            f"'{self.variable_workers.name}'",
        )

    def test_different_variables_do_not_clash(self):
        """The rule is checked per variable"""
        self._create_value("1", self.env_prod, server_id=self.server_test_1.id)
        self._create_value(
            "1",
            self.env_prod,
            variable=self.variable_other,
            server_id=self.server_test_1.id,
        )

    def test_environments_not_allowed(self):
        """Environments are rejected on Jet, Server Template
        and Plan Line Action values
        """
        for links in (
            {"jet_id": self.jet_sample.id},
            {"server_template_id": self.server_template_sample.id},
            {"plan_line_action_id": self.plan_line_1_action_1.id},
        ):
            with self.subTest(links=links), self.assertRaises(ValidationError):
                self._create_value("1", self.env_prod, **links)

        # Setting environments later is rejected too
        jet_value = self._create_value("1", jet_id=self.jet_sample.id)
        with self.assertRaises(ValidationError):
            jet_value.environment_ids = self.env_prod

    def test_change_variable_of_global_value(self):
        """Changing only the variable moves a global value into another scope.
        The rule must be checked there too.
        """
        self._create_value("1", variable=self.variable_other)
        self._create_value("1", self.env_prod, variable=self.variable_other)

        untagged = self._create_value("2")
        with self.assertRaises(ValidationError):
            untagged.variable_id = self.variable_other

        prod = self._create_value("3", self.env_prod)
        with self.assertRaises(ValidationError):
            prod.variable_id = self.variable_other

    def test_jet_template_sql_constraint_dropped(self):
        """Two Jet Template values of the same variable can exist
        if their environments differ
        """
        self.env.cr.execute(
            "SELECT 1 FROM pg_constraint WHERE conname = %s",
            ["cx_tower_variable_value_unique_variable_value_jet_template"],
        )
        self.assertFalse(self.env.cr.fetchall())

        prod = self._create_value(
            "8", self.env_prod, jet_template_id=self.jet_template_sample.id
        )
        dev = self._create_value(
            "2", self.env_dev, jet_template_id=self.jet_template_sample.id
        )
        self.env.flush_all()
        self.assertEqual(prod.jet_template_id, dev.jet_template_id)

    def test_reference_suffix(self):
        """A second value of the same variable on the same record
        gets a reference with a suffix
        """
        untagged = self._create_value("2", server_id=self.server_test_1.id)
        prod = self._create_value("8", self.env_prod, server_id=self.server_test_1.id)
        self.assertEqual(prod.reference, f"{untagged.reference}_2")

    def test_reference_suffix_same_batch(self):
        """Values of the same variable saved together get unique references"""
        server = self._create_server()
        server.write(
            {
                "variable_value_ids": [
                    (
                        0,
                        0,
                        {"variable_id": self.variable_workers.id, "value_char": "2"},
                    ),
                    (
                        0,
                        0,
                        {
                            "variable_id": self.variable_workers.id,
                            "value_char": "8",
                            "environment_ids": [(6, 0, self.env_prod.ids)],
                        },
                    ),
                ]
            }
        )
        values = server.variable_value_ids.filtered(
            lambda v: v.variable_id == self.variable_workers
        )
        self.assertEqual(len(values), 2)
        self.assertEqual(len(set(values.mapped("reference"))), 2)
