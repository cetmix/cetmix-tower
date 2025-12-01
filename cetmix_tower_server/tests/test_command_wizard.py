# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

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

    def test_custom_variable_value_ids_creation(self):
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

        # Trigger onchange to generate custom_variable_value_ids
        wizard._onchange_command_variable_ids()

        # Check that custom variable values were created
        self.assertEqual(len(wizard.custom_variable_value_ids), 2)

        # Check char variable value
        char_value = wizard.custom_variable_value_ids.filtered(
            lambda v: v.variable_id == variable
        )
        self.assertTrue(char_value)
        self.assertEqual(char_value.value_char, "server value")

        # Check option variable value
        option_value = wizard.custom_variable_value_ids.filtered(
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

    def test_custom_variable_value_ids_with_manager_access(self):
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

        # Trigger onchange to generate custom_variable_value_ids
        wizard._onchange_command_variable_ids()

        # Modify variable value
        wizard.custom_variable_value_ids.filtered(
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

    def test_default_applicability_for_regular_and_manager(self):
        """sets applicability='this' for regular users, keeps default for managers."""
        # Regular user (no special groups)
        default_usr = (
            self.env["cx.tower.command.run.wizard"]
            .with_user(self.user_bob)
            .default_get(["applicability"])
        )
        self.assertEqual(default_usr.get("applicability"), "this")

        # Manager user should receive the original default ("shared")
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        default_mgr = (
            self.env["cx.tower.command.run.wizard"]
            .with_user(self.user_bob)
            .default_get(["applicability"])
        )
        self.assertEqual(default_mgr.get("applicability"), "shared")

    def test_compute_show_servers_behavior(self):
        """Should enforce 'this' for regular users but preserve manager choice."""
        # Grant Bob the basic 'user' group so he can read servers and create the wizard
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")

        # Ensure Bob has read access to the first server
        self.server_test_1.write({"user_ids": [(4, self.user_bob.id)]})
        # Create a second server and grant Bob read access to it
        srv2 = self.Server.create(
            {
                "name": "Server 2",
                "ip_v4_address": "127.0.0.2",
                "ssh_username": "root",
                "ssh_password": "pwd",
                "ssh_auth_mode": "p",
                "os_id": self.os_debian_10.id,
            }
        )
        srv2.write({"user_ids": [(4, self.user_bob.id)]})

        # --- Regular user scenario ---
        wiz_usr = (
            self.env["cx.tower.command.run.wizard"]
            .with_user(self.user_bob)
            .create({"server_ids": [self.server_test_1.id, srv2.id]})
        )
        # Compute show_servers under Bob; he should see both servers
        wiz_usr._compute_show_servers()
        self.assertTrue(wiz_usr.show_servers)
        # Enforcement should set applicability to 'this'
        self.assertEqual(wiz_usr.applicability, "this")

        # --- Manager user scenario ---
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        # Grant Bob manager access to both servers
        self.server_test_1.write({"manager_ids": [(4, self.user_bob.id)]})
        srv2.write({"manager_ids": [(4, self.user_bob.id)]})

        wiz_mgr = (
            self.env["cx.tower.command.run.wizard"]
            .with_user(self.user_bob)
            .create({"server_ids": [self.server_test_1.id, srv2.id]})
        )
        # Compute show_servers under Bob as manager
        wiz_mgr._compute_show_servers()
        # Manager should also see both servers
        self.assertTrue(wiz_mgr.show_servers)
        # Enforcement should not override manager's choice of 'shared'
        self.assertEqual(wiz_mgr.applicability, "shared")

    def test_required_variable_validation(self):
        """
        Wizard must block execution when a required variable is empty
        and allow it after the value is provided.
        """
        # Create a required variable
        var = self.Variable.create(
            {
                "name": "Req Var",
                "reference": "req_var",
                "variable_type": "s",
            }
        )
        self.VariableValue.create(
            {
                "variable_id": var.id,
                "server_id": self.server_test_1.id,
                "required": True,
                "value_char": "",
            }
        )

        # Create command that uses this variable
        cmd = self.Command.create(
            {
                "name": "Echo Req Var",
                "action": "ssh_command",
                "code": "echo {{ req_var }}",
                "variable_ids": [(4, var.id)],
            }
        )

        self.server_test_1.write({"user_ids": [(4, self.manager.id)]})

        # Create wizard as manager user
        wiz = (
            self.env["cx.tower.command.run.wizard"]
            .with_user(self.manager)
            .create(
                {
                    "server_ids": [self.server_test_1.id],
                    "command_id": cmd.id,
                }
            )
        )

        # Create lines of configuration
        wiz._onchange_command_variable_ids()
        wiz._compute_has_missing_required_values()

        # Test blocking behavior
        self.assertTrue(wiz.has_missing_required_values)
        with self.assertRaises(ValidationError):
            wiz.run_command_on_server()

        # Fill the value directly in the wizard line
        wiz.custom_variable_value_ids.filtered(
            lambda line: line.variable_id == var
        ).value_char = "filled"

        # Recompute the flag
        wiz._compute_has_missing_required_values()
        self.assertFalse(wiz.has_missing_required_values)

        # Now the execution should pass
        wiz.run_command_on_server()
