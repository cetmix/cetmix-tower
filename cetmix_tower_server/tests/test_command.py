from odoo.exceptions import AccessError
from odoo.tests.common import Form

from .common import TestTowerCommon


class TestTowerCommand(TestTowerCommon):
    def test_sudo_command_prepare_method(self):
        """Test sudo command preparing in different modes"""

        server = self.server_test_1

        single_command = "ls -a /tmp"
        multiple_commands = "ls -a /tmp && mkdir /tmp/test"

        sudo_mode = "p"
        # Prepare single command for sudo with password
        cmd = server._prepare_command_for_sudo(single_command, sudo_mode)
        self.assertEqual(
            cmd,
            [single_command],
            msg=(
                "Single command for sudo with password should be "
                "equal to list with the original command"
                "as an only element"
            ),
        )
        # Prepare multiple commands for sudo with password
        cmd = server._prepare_command_for_sudo(multiple_commands, sudo_mode)
        self.assertEqual(
            cmd,
            [
                "ls -a /tmp",
                "mkdir /tmp/test",
            ],
            msg=(
                "Multiple commands with sudo with password should be "
                "a list of separated commands from original line"
            ),
        )

        sudo_mode = "n"
        # Prepare single command for sudo without password
        cmd = server._prepare_command_for_sudo(single_command, sudo_mode)
        self.assertEqual(
            cmd,
            f"sudo -S -p '' {single_command}",
            msg=(
                "Single command with sudo without password should be "
                "equal to the original command prefixed with \"sudo -S -p ''\""
            ),
        )
        # Prepare multiple commands for sudo without password
        cmd = server._prepare_command_for_sudo(multiple_commands, sudo_mode)
        self.assertEqual(
            cmd,
            "sudo -S -p '' ls -a /tmp && sudo -S -p '' mkdir /tmp/test",
            msg=(
                "Multiple commands with sudo with password should be "
                "a re-joined string from list of separated original "
                "each prefixed with \"sudo -S -p ''\""
            ),
        )

    def test_render_code(self):
        """Test code template rendering"""

        # Only 'test_path_' must be rendered
        args = {"test_path_": "/tmp", "test_os": "debian"}
        res = self.command_create_dir.render_code(**args)
        rendered_code = res.get(self.command_create_dir.id)
        rendered_code_expected = "cd /tmp && mkdir "
        self.assertEqual(
            rendered_code,
            rendered_code_expected,
            msg="Must be rendered as '{}'".format(rendered_code_expected),
        )

        # 'test_path_' and 'dir' must be rendered
        args = {"test_path_": "/tmp", "os": "debian", "test_dir": "odoo"}
        res = self.command_create_dir.render_code(**args)
        rendered_code = res.get(self.command_create_dir.id)
        self.assertEqual(
            rendered_code,
            "cd /tmp && mkdir odoo",
            msg="Must be rendered as 'cd /tmp && mkdir odoo'",
        )

    def test_execute_command_with_variables(self):
        """Test code executing and command log records"""

        # Save variable values for Server 1
        with Form(self.server_test_1) as f:
            with f.variable_value_ids.new() as line:
                line.variable_id = self.variable_dir
                line.value_char = "test-odoo-1"
            with f.variable_value_ids.new() as line:
                line.variable_id = self.variable_path
                line.value_char = "/opt/tower"
            f.save()

        # Add label to track command log
        command_label = "Test Command #1"
        custom_values = {"log": {"label": command_label}}

        # Execute command for Server 1
        self.server_test_1.execute_command(self.command_create_dir, **custom_values)

        # Expected rendered command code
        rendered_code_expected = "cd /opt/tower && mkdir test-odoo-1"

        # Get command log
        log_record = self.CommandLog.search([("label", "=", command_label)])

        # Check log values
        self.assertEqual(len(log_record), 1, msg="Must be a single log record")
        self.assertEqual(
            log_record.server_id.id,
            self.server_test_1.id,
            msg="Record must belong to Test 1",
        )
        self.assertEqual(
            log_record.command_id.id,
            self.command_create_dir.id,
            msg="Record must belong to command 'Create dir'",
        )
        self.assertEqual(
            log_record.code,
            rendered_code_expected,
            msg="Rendered code must be '{}'".format(rendered_code_expected),
        )
        self.assertEqual(
            log_record.command_status, 0, msg="Command status must be equal to 0"
        )

    def test_command_with_keys(self):
        """Test command with keys in code"""

        # Command
        code = "cd {{ test_path_ }} && mkdir #!cxtower.secret.FOLDER"
        command_with_keys = self.Command.create(
            {"name": "Command with keys", "code": code}
        )

        # Key
        self.Key.create(
            {
                "name": "Folder",
                "key_ref": "FOLDER",
                "secret_value": "secretFolder",
                "key_type": "s",
            }
        )

        # Parse command with key parser to ensure key is parsed correctly
        code_parsed_expected = "cd {{ test_path_ }} && mkdir secretFolder"
        code_parsed = self.Key.parse_code(code)
        self.assertEqual(
            code_parsed,
            code_parsed_expected,
            msg="Parsed code doesn't match expected one",
        )

        # Save variable values for Server 1
        with Form(self.server_test_1) as f:
            with f.variable_value_ids.new() as line:
                line.variable_id = self.variable_path
                line.value_char = "/opt/tower"
            f.save()

        # Add label to track command log
        command_label = "Test Command with keys"
        custom_values = {"log": {"label": command_label}}

        # Execute command for Server 1
        self.server_test_1.execute_command(command_with_keys, **custom_values)

        # Expected rendered command code
        rendered_code_expected = "cd /opt/tower && mkdir #!cxtower.secret.FOLDER"

        # Get command log
        log_record = self.CommandLog.search([("label", "=", command_label)])

        # Check log values
        self.assertEqual(len(log_record), 1, msg="Must be a single log record")
        self.assertEqual(
            log_record.server_id.id,
            self.server_test_1.id,
            msg=("Record must belong %s", self.server_test_1.name),
        )
        self.assertEqual(
            log_record.command_id.id,
            command_with_keys.id,
            msg=("Record must belong to command %s", command_with_keys.name),
        )
        self.assertEqual(
            log_record.code,
            rendered_code_expected,
            msg="Rendered code must be '{}'".format(rendered_code_expected),
        )
        self.assertEqual(
            log_record.command_status, 0, msg="Command status must be equal to 0"
        )

    def test_user_access_rule(self):
        """Test user access rule"""
        # Create the test command
        test_command = self.Command.create({"name": "Test command"})

        # Ensure that defaulf command access_level is equal to 2
        self.assertEqual(test_command.access_level, "2")
        # Remove bob from all cxtower_server groups
        self.remove_from_group(
            self.user_bob,
            [
                "cetmix_tower_server.group_user",
                "cetmix_tower_server.group_manager",
                "cetmix_tower_server.group_root",
            ],
        )
        # Ensure that regular user cannot access the command
        test_command_1_as_bob = test_command.with_user(self.user_bob)
        with self.assertRaises(AccessError):
            command_name = test_command_1_as_bob.name
        test_command.write({"access_level": "1"})
        # Add user to group
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")
        # Ensure that user can access the command
        command_name = test_command_1_as_bob.name
        self.assertEqual(command_name, "Test command", msg="Must return 'Test command'")
        # Add user to group_manager
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        # Create a new command with access_level 1
        new_command = self.Command.with_user(self.user_bob).create(
            {"name": "New Test Command", "access_level": "1"}
        )
        self.assertEqual(new_command.access_level, "1")
        # Try to elevate the access_level of new_command to 2
        new_command.with_user(self.user_bob).write({"access_level": "2"})
        self.assertEqual(new_command.access_level, "2")

        # Ensure that manager user cannot see commands with access_level 3

        restricted_command = self.Command.create(
            {"name": "Restricted Command", "access_level": "3"}
        )

        user_bob_records = (
            self.env["cx.tower.command"].with_user(self.user_bob).search([])
        )
        user_bob_records_access_level_3 = user_bob_records.filtered(
            lambda r: r.access_level == "3"
        )
        self.assertFalse(user_bob_records_access_level_3, "Must return 0 records")
        # Add user to group_root
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_root")
        # Ensure that root user can see commands with access_level 3
        user_bob_records = (
            self.env["cx.tower.command"].with_user(self.user_bob).search([])
        )
        user_bob_records_access_level_3 = user_bob_records.filtered(
            lambda r: r.access_level == "3"
        )
        self.assertTrue(user_bob_records_access_level_3, "Must not be empty")

        # Try to demote the access_level of new_command to 2
        restricted_command.with_user(self.user_bob).write({"access_level": "2"})
        self.assertEqual(restricted_command.access_level, "2")
        # Checking the case that may require clearing the cache:
        # Create a command with "Manager" access level.
        cc_command = self.Command.create({"name": "CC Command", "access_level": "2"})

        # Remove bob from all cxtower_server groups
        self.remove_from_group(
            self.user_bob,
            [
                "cetmix_tower_server.group_user",
                "cetmix_tower_server.group_manager",
                "cetmix_tower_server.group_root",
            ],
        )
        # Add user to group
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")
        # Check command list with "Tower-User" user. User cannot see this command.
        with self.assertRaises(AccessError):
            command_name = cc_command.with_user(self.user_bob).name
        # Change the command access level to "User".
        cc_command.write({"access_level": "1"})

        command_name = cc_command.with_user(self.user_bob).name
        self.assertEqual(command_name, "CC Command", msg="Must return 'CC command'")
