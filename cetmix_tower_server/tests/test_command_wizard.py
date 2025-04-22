from odoo.exceptions import AccessError, ValidationError

from .common import TestTowerCommon


class TestTowerCommandWizard(TestTowerCommon):
    """Test Tower Command Run Wizard"""

    def test_user_access_rules(self):
        """Test user access rules"""

        # Add Bob to `root` group in order to create a wizard
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_root")

        # Create new wizard
        test_wizard = (
            self.env["cx.tower.command.run.wizard"]
            .with_user(self.user_bob)
            .create(
                {
                    "server_ids": [self.server_test_1.id],
                    "command_id": self.command_create_dir.id,
                }
            )
        ).with_user(self.user_bob)

        # Force rendered code computation
        test_wizard._compute_rendered_code()

        # Remove bob from all cxtower_server groups
        self.remove_from_group(
            self.user_bob,
            [
                "cetmix_tower_server.group_user",
                "cetmix_tower_server.group_manager",
                "cetmix_tower_server.group_root",
            ],
        )
        # Ensure that regular user cannot execute command in wizard
        with self.assertRaises(AccessError):
            test_wizard.run_command_in_wizard()

        # Add bob back to `user` group and try again
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")
        with self.assertRaises(AccessError):
            test_wizard.run_command_in_wizard()

        # Now promote bob to `manager` group and try again
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        test_wizard.run_command_in_wizard()

    def test_execute_code_without_a_command(self):
        """Run command code without a command selected"""

        # Add Bob to `root` group in order to create a wizard
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_root")

        # Create new wizard
        test_wizard = (
            self.env["cx.tower.command.run.wizard"]
            .with_user(self.user_bob)
            .create(
                {
                    "server_ids": [self.server_test_1.id],
                }
            )
        ).with_user(self.user_bob)

        # Should not allow to run command on server if no command is selected
        with self.assertRaises(ValidationError):
            test_wizard.run_command_on_server()

    def test_run_command_on_server_access_rights(self):
        """Test access rights for executing command on server"""

        # Add Bob to `root` group
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_root")

        # Create new wizard with Bob as a root user
        test_wizard = (
            self.env["cx.tower.command.run.wizard"]
            .with_user(self.user_bob)
            .create(
                {
                    "server_ids": [self.server_test_1.id],
                    "command_id": self.command_create_dir.id,
                }
            )
        ).with_user(self.user_bob)

        # Ensure command can be executed by root
        test_wizard.run_command_on_server()

        # Remove Bob from all tower server groups
        self.remove_from_group(
            self.user_bob,
            [
                "cetmix_tower_server.group_user",
                "cetmix_tower_server.group_manager",
                "cetmix_tower_server.group_root",
            ],
        )

        # Ensure that regular user cannot execute command on server
        with self.assertRaises(AccessError):
            test_wizard.run_command_on_server()

        #  Add Bob to `user` group and ensure he can execute commands
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")
        test_wizard.run_command_on_server()
        # Ensure that Bob has access to path field but can't read its value
        allowed_path = (
            self.user_bob.has_group("cetmix_tower_server.group_manager")
            and test_wizard.path
        )

        self.assertEqual(allowed_path, False)
        # Ensure that Bob can write to the path field as a member of `group_user`
        # the result will be None
        test_wizard.write({"path": "/new/invalid/path"})
        allowed_path = (
            test_wizard.path
            if self.user_bob.has_group("cetmix_tower_server.group_manager")
            and test_wizard.path
            else None
        )
        self.assertEqual(allowed_path, None)

        # Add Bob to `manager` group and ensure access to execute commands
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        test_wizard.run_command_on_server()
        # Check that path access is valid for the manager
        test_wizard.read(["path"])

    def test_run_command_with_sensitive_vars_on_server_access_rights(self):
        """Test access rights for executing command on server"""
        # create new command
        command = self.Command.create(
            {
                "name": "Create new command",
                "action": "python_code",
                "code": """
        properties = {
            "Server Name": {{ tower.server.name }},
            "Server Reference": {{ tower.server.reference }},
            "SSH Username": {{ tower.server.username }},
            "IPv4 Address": {{ tower.server.ipv4 }},
            "IPv6 Address": {{ tower.server.ipv6 }},
            "Partner Name": {{ tower.server.partner_name }}
        }
        result = {"exit_code": 0, "message": properties}
                        """,
                "access_level": "1",
            }
        )

        # Add Bob to `root` group in order to create a wizard
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_root")

        server = self.Server.with_user(self.user_bob).create(
            {
                "name": "Test 2",
                "ip_v4_address": "localhost",
                "ssh_username": "root",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "os_id": self.os_debian_10.id,
            }
        )

        self.remove_from_group(
            self.user_bob,
            [
                "cetmix_tower_server.group_user",
                "cetmix_tower_server.group_manager",
                "cetmix_tower_server.group_root",
            ],
        )

        # Add user bob to group user
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")

        # Create new wizard with Bob
        test_wizard = (
            self.env["cx.tower.command.run.wizard"]
            .with_user(self.user_bob)
            .create(
                {
                    "server_ids": [server.id],
                    "command_id": command.id,
                }
            )
        ).with_user(self.user_bob)

        # Add Bob as a user to the command
        command.write({"user_ids": [(4, self.user_bob.id)]})

        # Ensure command can be executed by user
        test_wizard.run_command_on_server()

    def test_run_command_in_wizard_multiple_servers(self):
        """
        Test that raises an error when multiple servers are selected
        """

        # Add Bob to `root` group in order to create a wizard

        server_test_2 = self.Server.create(
            {
                "name": "Test 2",
                "ip_v4_address": "localhost",
                "ssh_username": "root",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "os_id": self.os_debian_10.id,
            }
        )

        self.add_to_group(self.user_bob, "cetmix_tower_server.group_root")

        # Create new wizard with multiple servers selected
        test_wizard = (
            self.env["cx.tower.command.run.wizard"]
            .with_user(self.user_bob)
            .create(
                {
                    "server_ids": [self.server_test_1.id, server_test_2.id],
                    "command_id": self.command_create_dir.id,
                }
            )
        ).with_user(self.user_bob)

        # Force rendered code computation
        test_wizard._compute_rendered_code()

        # Ensure that executing command with multiple servers
        # selected raises a ValidationError
        with self.assertRaises(
            ValidationError,
            msg="You cannot run custom code on multiple servers at once.",
        ):
            test_wizard.run_command_in_wizard()

        # Now, test with a single server selected
        test_wizard.server_ids = [self.server_test_1.id]

        # Ensure that executing command works with a single server selected
        test_wizard.run_command_in_wizard()
        self.assertTrue(
            test_wizard.result,
            msg="Command execution should succeed with a single server selected",
        )

    def test_custom_variable_values_creation(self):
        """
        Test that custom variable values are created properly
        when command has variables
        """
        # Add manager as server user
        self.server_test_1.write({"user_ids": [(4, self.manager.id)]})

        # Create variables that will be used in command
        variable = self.Variable.create(
            {
                "name": "Test Variable",
                "reference": "test_var",
                "variable_type": "s",  # string type
            }
        )
        option_variable = self.Variable.create(
            {
                "name": "Option Variable",
                "reference": "opt_var",
                "variable_type": "o",  # option type
            }
        )
        option = self.VariableOption.create(
            {
                "name": "Test Option",
                "value_char": "option_value",
                "variable_id": option_variable.id,
            }
        )

        # Add variable values to server
        self.VariableValue.create(
            [
                {
                    "variable_id": variable.id,
                    "server_id": self.server_test_1.id,
                    "value_char": "server value",
                },
                {
                    "variable_id": option_variable.id,
                    "server_id": self.server_test_1.id,
                    "value_char": "option_value",
                },
            ]
        )

        # Create command that uses these variables in its code
        command = self.Command.create(
            {
                "name": "Test Command with Variables",
                "action": "ssh_command",
                "code": "echo {{ test_var }} && echo {{ opt_var }}",
            }
        )

        # Create wizard
        wizard = (
            self.env["cx.tower.command.run.wizard"]
            .with_user(self.manager)
            .create(
                {
                    "server_ids": [self.server_test_1.id],
                    "command_id": command.id,
                    "action": "ssh_command",
                }
            )
        )

        # Trigger onchange to generate custom_variable_values
        wizard._onchange_command_variable_ids()

        # Check that custom variable values were created
        self.assertEqual(len(wizard.custom_variable_values), 2)

        # Check char variable value
        char_value = wizard.custom_variable_values.filtered(
            lambda v: v.variable_id == variable
        )
        self.assertTrue(char_value)
        self.assertEqual(char_value.value_char, "server value")

        # Check option variable value
        option_value = wizard.custom_variable_values.filtered(
            lambda v: v.variable_id == option_variable
        )
        self.assertTrue(option_value)
        self.assertEqual(option_value.value_char, "option_value")
        self.assertEqual(option_value.option_id, option)

        # Try to change variable value when user doesn't have write access
        char_value.value_char = "custom value"

        # Run command
        wizard.run_command_on_server()

        # Get latest command log
        command_log = self.env["cx.tower.command.log"].search(
            [
                ("server_id", "=", self.server_test_1.id),
                ("command_id", "=", command.id),
            ],
            order="create_date desc",
            limit=1,
        )

        # Verify that original server values were used
        self.assertEqual(command_log.code, "echo server value && echo option_value")

    def test_custom_variable_values_with_manager_access(self):
        """
        Test that custom variable values are applied
        when manager has write access
        """
        # Add manager as server manager
        self.server_test_1.write({"manager_ids": [(4, self.manager.id)]})

        # Create variables that will be used in command
        variable = self.Variable.create(
            {
                "name": "Test Variable",
                "reference": "test_var",
                "variable_type": "s",  # string type
            }
        )

        # Add variable value to server
        self.VariableValue.create(
            {
                "variable_id": variable.id,
                "server_id": self.server_test_1.id,
                "value_char": "server value",
            }
        )

        # Create command that uses the variable
        command = self.Command.create(
            {
                "name": "Test Command with Variables",
                "action": "ssh_command",
                "code": "echo {{ test_var }}",
            }
        )

        # Create wizard
        wizard = (
            self.env["cx.tower.command.run.wizard"]
            .with_user(self.manager)
            .create(
                {
                    "server_ids": [self.server_test_1.id],
                    "command_id": command.id,
                    "action": "ssh_command",
                }
            )
        )

        # Trigger onchange to generate custom_variable_values
        wizard._onchange_command_variable_ids()

        # Modify variable value
        wizard.custom_variable_values.filtered(
            lambda v: v.variable_id == variable
        ).value_char = "manager value"

        # Run command
        wizard.run_command_on_server()

        # Get latest command log
        command_log = self.env["cx.tower.command.log"].search(
            [
                ("server_id", "=", self.server_test_1.id),
                ("command_id", "=", command.id),
            ],
            order="create_date desc",
            limit=1,
        )

        # Verify that custom value was used
        self.assertEqual(command_log.code, "echo manager value")
