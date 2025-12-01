# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from datetime import timedelta
from unittest.mock import patch

from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Datetime
from odoo.tests import Form
from odoo.tools import mute_logger

from ..models.constants import (
    ANOTHER_COMMAND_RUNNING,
    COMMAND_TIMED_OUT,
    COMMAND_TIMED_OUT_MESSAGE,
    GENERAL_ERROR,
)
from .common import TestTowerCommon


class TestTowerCommand(TestTowerCommon):
    """
    Test the command model.

    Important!
    As this model inherits from the `cx.tower.template.mixin`
    we will tests template rendering methods in this class too.

    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Save variable values for Server 1
        with Form(cls.server_test_1) as f:
            with f.variable_value_ids.new() as line:
                line.variable_id = cls.variable_dir
                line.value_char = "test-odoo-1"
            with f.variable_value_ids.new() as line:
                line.variable_id = cls.variable_path
                line.value_char = "/opt/tower"
            f.save()

        # Secret key
        cls.secret_folder_key = cls.Key.create(
            {
                "name": "Folder",
                "reference": "FOLDER",
                "secret_value": "secretFolder",
                "key_type": "s",
            }
        )
        cls.secret_python_key = cls.Key.create(
            {
                "name": "python",
                "reference": "PYTHON",
                "secret_value": "secretPythonCode",
                "key_type": "s",
            }
        )

        # secret value as multi line string
        cls.python_ssh_key = cls.Key.create(
            {
                "name": "Test Python SSH Key",
                "reference": "test_python_ssh_key",
                "key_type": "s",
                "secret_value": """
                Python
                much
                key
                """,
            }
        )

        cls.secret_test_rsa_key = cls.Key.create(
            {
                "name": "test rsa",
                "reference": "test_rsa",
                "secret_value": """-----BEGIN RSA PRIVATE KEY-----
SuchMuchSecretKey
-----END RSA PRIVATE KEY----- """,
                "key_type": "s",
            }
        )
        # Command
        cls.command_create_new_command = cls.Command.create(
            {
                "name": "Create new command",
                "action": "python_code",
                "code": """
server_name = {{ tower.server.name }}
if server_name and #!cxtower.secret.FOLDER!# == "secretFolder":
    # We don't actually create a new command because it will raise
    # access error if user doesn't have access to 'create' operation.
    # Instead we just return a dummy command result.
    command = "new command"
    result = {"exit_code": 0, "message": "New command was created"}
else:
    result = {"exit_code": -100, "message": "error"}
    """,
            }
        )

        cls.command_python_command_1 = cls.Command.create(
            {
                "name": "Python command with secret #1",
                "action": "python_code",
                "code": """
result = {
    "exit_code": 0,
    "message": #!cxtower.secret.PYTHON!#,
}
    """,
            }
        )

        cls.command_python_command_2 = cls.Command.create(
            {
                "name": "Python command with secret #2",
                "action": "python_code",
                "code": """
result = {
    "exit_code": 0,
    "message": 'We use #!cxtower.secret.PYTHON!#' ,
}
    """,
            }
        )

        cls.command_python_command_3 = cls.Command.create(
            {
                "name": "Python command with secret #3",
                "action": "python_code",
                "code": """
result = {
    "exit_code": 0,
    "message": ""#!cxtower.secret.test_rsa!#"" ,
}
    """,
            }
        )

        cls.command_python_command_4 = cls.Command.create(
            {
                "name": "Python command with secret #4",
                "action": "python_code",
                "code": """
top_secret = #!cxtower.secret.test_python_ssh_key!#
result = {
    "exit_code": 0,
    "message": top_secret ,
}
    """,
            }
        )
        cls.server = cls.Server.create(
            {
                "name": "Test Server",
                "user_ids": [(6, 0, [cls.user.id])],
                "manager_ids": [(6, 0, [cls.manager.id])],
                "ssh_username": "test",
                "ssh_password": "test",
                "ip_v4_address": "127.0.0.1",
            }
        )

    def _create_command(self, **kwargs):
        """Helper to create a command record with default values."""
        vals = {
            "name": "Test Command",
            "access_level": "1",  # override default
            "user_ids": [(6, 0, [])],
            "manager_ids": [(6, 0, [])],
            "server_ids": [(6, 0, [])],
        }
        if kwargs:
            vals.update(kwargs)
        return self.Command.create(vals)

    def test_user_read_access(self):
        """
        For a user:
          Read access is allowed if access_level == "1" and either the command's
          own user_ids includes the user OR a related server (via server_ids)
          includes the user in its user_ids.
        """
        # Case 1: Command with access_level "1" and user in command.user_ids.
        cmd1 = self._create_command(
            **{
                "access_level": "1",
                "user_ids": [(6, 0, [self.user.id])],
            }
        )
        recs1 = self.Command.with_user(self.user).search([("id", "=", cmd1.id)])
        self.assertIn(
            cmd1,
            recs1,
            "User should see the command if in command.user_ids"
            " and access_level == '1'.",
        )

        # Case 2: Command with access_level "1" and user not in command.user_ids
        # but in a related server.
        cmd2 = self._create_command(
            **{
                "access_level": "1",
                "user_ids": [(6, 0, [])],
                "server_ids": [(6, 0, [self.server.id])],
            }
        )
        recs2 = self.Command.with_user(self.user).search([("id", "=", cmd2.id)])
        self.assertIn(
            cmd2,
            recs2,
            "User should see the command if related server.user_ids includes the user.",
        )

        # Negative: If access_level is "1" but neither command.user_ids
        # nor server_ids.user_ids includes the user.
        cmd3 = self._create_command(
            **{
                "access_level": "1",
                "user_ids": [(6, 0, [])],
                "server_ids": [(6, 0, [])],
            }
        )
        recs3 = self.Command.with_user(self.user).search([("id", "=", cmd3.id)])
        self.assertNotIn(
            cmd3,
            recs3,
            "User should not see the command if not granted access.",
        )

    def test_manager_read_access(self):
        """
        For a manager:
          Allowed to read a command if access_level <= "2" AND
          (either the command itself grants access via user_ids or manager_ids
           OR there are no related servers OR a related server grants access via
            its user_ids or manager_ids).
        """
        # Case 1: Command with access_level "2" and command.manager_ids
        #  includes the manager but the server is not related to the command.
        another_server = self.Server.create(
            {
                "name": "Another Server",
                "ip_v4_address": "127.0.0.2",
                "ssh_username": "test",
                "ssh_password": "test",
                "user_ids": [(6, 0, [])],
                "manager_ids": [(6, 0, [])],
            }
        )
        cmd1 = self._create_command(
            **{
                "access_level": "2",
                "manager_ids": [(6, 0, [self.manager.id])],
                "server_ids": [(6, 0, [another_server.id])],
            }
        )
        recs1 = self.Command.with_user(self.manager).search([("id", "=", cmd1.id)])
        self.assertIn(
            cmd1,
            recs1,
            "Manager should see the command if in command.manager_ids"
            " and access_level <= '2'.",
        )

        # Case 2: Command with access_level "2" that does not grant access
        #  on the command itself, but a related server grants access via
        # but a related server grants access via its manager_ids.
        cmd2 = self._create_command(
            **{
                "access_level": "2",
                "user_ids": [(6, 0, [])],
                "manager_ids": [(6, 0, [])],
                "server_ids": [(6, 0, [self.server.id])],
            }
        )
        recs2 = self.Command.with_user(self.manager).search([("id", "=", cmd2.id)])
        self.assertIn(
            cmd2,
            recs2,
            "Manager should see the command if related server.manager_ids"
            " includes the manager.",
        )

        # Positive: Command with access_level "2" without any granted access.
        cmd3 = self._create_command(
            **{
                "access_level": "2",
                "user_ids": [(6, 0, [])],
                "manager_ids": [(6, 0, [])],
                "server_ids": [(6, 0, [])],
            }
        )
        recs3 = self.Command.with_user(self.manager).search([("id", "=", cmd3.id)])
        self.assertIn(
            cmd3,
            recs3,
            "Manager should see the command if not granted access "
            "but not related to any server.",
        )

        # Case 3: Remove from manager in the cmd1.
        # Should not see the command because it belongs to another server.
        cmd1.manager_ids = [(3, self.manager.id)]
        recs4 = self.Command.with_user(self.manager).search([("id", "=", cmd1.id)])
        self.assertNotIn(
            cmd1,
            recs4,
            "Manager should not see the command if "
            "removed from command.manager_ids."
            " and command belongs to another server.",
        )

    def test_manager_write_create_access(self):
        """
        For a manager:
          Allowed to write and create a command if access_level <= "2" AND
          the command's own manager_ids includes the manager.
        """
        # Case: Command with access_level "2" and manager_ids includes the manager.
        cmd1 = self._create_command(
            **{
                "access_level": "2",
                "manager_ids": [(6, 0, [self.manager.id])],
            }
        )
        try:
            cmd1.with_user(self.manager).write({"name": "Manager Updated Command"})
        except AccessError:
            self.fail(
                "Manager should be able to update the command "
                "if in command.manager_ids."
            )
        self.assertEqual(cmd1.with_user(self.manager).name, "Manager Updated Command")

        # Attempt to create a command as manager without including their ID
        #  in manager_ids should fail.
        cmd_invalid_vals = {
            "name": "Invalid Manager Create",
            "access_level": "2",
            "manager_ids": [(6, 0, [])],
            "action": "python_code",
            "code": "print('dummy')",
        }
        with self.assertRaises(AccessError):
            self.Command.with_user(self.manager).create(cmd_invalid_vals)

    def test_manager_unlink_access(self):
        """
        For a manager:
          Allowed to delete a command if access_level <= "2",
          the current user is the record creator,
          AND the command's own manager_ids includes the manager.
        """
        # Scenario 1: Command created by the manager with manager_ids
        # including the manager.
        cmd1 = self.Command.with_user(self.manager).create(
            {
                "name": "Manager Created Command",
                "access_level": "2",
            }
        )
        try:
            cmd1.with_user(self.manager).unlink()
        except AccessError:
            self.fail(
                "Manager should be able to delete a command "
                "they created if in command.manager_ids."
            )

        # Scenario 2: Command created by someone else
        # even if manager_ids includes the manager.
        cmd2 = self._create_command(
            **{
                "access_level": "2",
                "manager_ids": [(6, 0, [self.manager.id])],
            }
        )
        with self.assertRaises(AccessError):
            cmd2.with_user(self.manager).unlink()

    def test_root_unrestricted_access(self):
        """
        For a root user:
          Unlimited access: root can read, write, create, and delete commands
          regardless of access_level or related servers.
        """
        cmd = self._create_command(
            **{
                "access_level": "3",  # above the threshold for managers
            }
        )
        recs = self.Command.with_user(self.root).search([("id", "=", cmd.id)])
        self.assertIn(
            cmd,
            recs,
            "Root should see the command regardless of restrictions.",
        )
        try:
            cmd.with_user(self.root).write({"name": "Root Updated Command"})
        except AccessError:
            self.fail(
                "Root should be able to update the command " "without restrictions."
            )
        self.assertEqual(cmd.with_user(self.root).name, "Root Updated Command")
        cmd2 = self.Command.with_user(self.root).create(
            {
                "name": "Root Created Command",
                "access_level": "3",
                "action": "python_code",
                "code": "print('root')",
            }
        )
        self.assertTrue(
            cmd2,
            "Root should be able to create a command " "without restrictions.",
        )
        cmd2.with_user(self.root).unlink()
        recs_after = self.Command.with_user(self.root).search([("id", "=", cmd2.id)])
        self.assertFalse(
            recs_after,
            "Root should be able to delete the command without restrictions.",
        )

    def test_ssh_command_prepare_method_without_path(self):
        """Test ssh command preparation in different modes without path"""

        server = self.server_test_1

        single_command = "ls -a /tmp"
        multiple_commands = "ls -a /tmp && mkdir /tmp/test"

        sudo_mode = "p"

        # Prepare single command for sudo with password
        cmd = server._prepare_ssh_command(single_command, path=None, sudo=sudo_mode)
        self.assertEqual(
            cmd,
            [f"{self.sudo_prefix} {single_command}"],
            msg=(
                "Single command for sudo with password should be "
                "equal to list with the original command"
                "as an only element"
            ),
        )

        # Prepare multiple commands for sudo with password
        cmd = server._prepare_ssh_command(multiple_commands, path=None, sudo=sudo_mode)
        self.assertEqual(
            cmd,
            [
                f"{self.sudo_prefix} ls -a /tmp",
                f"{self.sudo_prefix} mkdir /tmp/test",
            ],
            msg=(
                "Multiple commands with sudo with password should be "
                "a list of separated commands from original line"
            ),
        )

        sudo_mode = "n"

        # Prepare single command for sudo without password
        cmd = server._prepare_ssh_command(single_command, path=None, sudo=sudo_mode)
        self.assertEqual(
            cmd,
            f"{self.sudo_prefix} {single_command}",
            msg=(
                "Single command with sudo without password should be "
                f'equal to the original command prefixed with "{self.sudo_prefix}"'
            ),
        )

        # Prepare multiple commands for sudo without password
        cmd = server._prepare_ssh_command(multiple_commands, path=None, sudo=sudo_mode)
        self.assertEqual(
            cmd,
            f"{self.sudo_prefix} ls -a /tmp && {self.sudo_prefix} mkdir /tmp/test",
            msg=(
                "Multiple commands with sudo with password should be "
                "a re-joined string from list of separated original "
                f'each prefixed with "{self.sudo_prefix}"'
            ),
        )

        # Prepare single command without sudo
        cmd = server._prepare_ssh_command(single_command)
        self.assertEqual(
            cmd,
            single_command,
            msg=(
                "Single command without sudo should be "
                "equal to the original command "
            ),
        )

        # Prepare multiple without sudo
        cmd = server._prepare_ssh_command(multiple_commands)
        self.assertEqual(
            cmd,
            multiple_commands,
            msg=(
                "Multiple commands without sudo should be "
                "equal to the original line of commands"
            ),
        )

    def test_ssh_command_prepare_method_with_path(self):
        """Test command preparation in different modes with path"""

        server = self.server_test_1

        single_command = "ls -a /tmp"
        multiple_commands = "ls -a /tmp && mkdir /tmp/test"
        path = "/home/doge"

        sudo_mode = "p"

        # Prepare single command for sudo with password
        cmd = server._prepare_ssh_command(single_command, path=path, sudo=sudo_mode)
        self.assertEqual(
            cmd,
            [f"cd {path}", f"{self.sudo_prefix} {single_command}"],
            msg=(
                "Single command for sudo with password should be "
                "equal to list of two elements:"
                " change directory and original command"
            ),
        )

        # Prepare multiple commands for sudo with password
        cmd = server._prepare_ssh_command(multiple_commands, path=path, sudo=sudo_mode)
        self.assertEqual(
            cmd,
            [
                f"cd {path}",
                f"{self.sudo_prefix} ls -a /tmp",
                f"{self.sudo_prefix} mkdir /tmp/test",
            ],
            msg=(
                "Multiple commands with sudo with password should be "
                "a list of separated commands from original line"
            ),
        )

        sudo_mode = "n"

        # Prepare single command for sudo without password
        cmd = server._prepare_ssh_command(single_command, path=path, sudo=sudo_mode)
        self.assertEqual(
            cmd,
            f"cd {path} && {self.sudo_prefix} {single_command}",
            msg=(
                "Single command with sudo without password should be "
                f'equal to the original command prefixed with "{self.sudo_prefix}"'
            ),
        )

        # Prepare multiple commands for sudo without password
        cmd = server._prepare_ssh_command(multiple_commands, path=path, sudo=sudo_mode)
        self.assertEqual(
            cmd,
            f"cd {path} && {self.sudo_prefix} ls -a /tmp && {self.sudo_prefix} mkdir /tmp/test",  # noqa
            msg=(
                "Multiple commands with sudo with password should be "
                "a re-joined string from list of separated original "
                f'each prefixed with "{self.sudo_prefix}"'
            ),
        )

        # Prepare single command without sudo
        cmd = server._prepare_ssh_command(single_command, path=path)
        self.assertEqual(
            cmd,
            f"cd {path} && {single_command}",
            msg=(
                "Single command for without sudo should be "
                "equal to the the original command"
                "with 'cd {{ path }} && ' prefix"
            ),
        )

        # Prepare multiple commands without sudo
        cmd = server._prepare_ssh_command(multiple_commands, path=path)
        self.assertEqual(
            cmd,
            f"cd {path} && {multiple_commands}",  # noqa
            msg=(
                "Multiple commands without sudo should be "
                "original command with 'change directory' command prepended"
            ),
        )

    def test_ssh_command_no_split_for_sudo_without_path(self):
        """If no_split_for_sudo=True, even '&&' shouldn’t split into a list."""
        server = self.server_test_1
        cmd_line = "echo a && echo b"
        sudo_mode = "p"
        result = server._prepare_ssh_command(
            cmd_line, sudo=sudo_mode, no_split_for_sudo=True
        )
        expected = [f"{self.sudo_prefix} {cmd_line}"]
        self.assertEqual(
            result, expected, "With no_split_for_sudo, '&&' must not produce a list"
        )

    def test_ssh_command_no_split_for_sudo_with_path(self):
        """Same, but with a custom cwd prefix."""
        server = self.server_test_1
        cmd_line = "echo a && echo b"
        path = "/tmp"
        sudo_mode = "p"
        result = server._prepare_ssh_command(
            cmd_line, path=path, sudo=sudo_mode, no_split_for_sudo=True
        )
        expected = [f"cd {path}", f"{self.sudo_prefix} {cmd_line}"]
        self.assertEqual(
            result,
            expected,
            "With no_split_for_sudo and path, the entire '&&' string remains un-split",
        )

    def test_server_render_command(self):
        """Test rendering command using `_render_command` method
        of cx.tower.server
        """

        # -- 1 --
        # Test with default path
        rendered_command = self.server_test_1._render_command(self.command_create_dir)
        rendered_code_expected = "cd /opt/tower && mkdir test-odoo-1"
        rendered_path_expected = f"/home/{self.server_test_1.ssh_username}"

        self.assertEqual(
            rendered_command["rendered_code"],
            rendered_code_expected,
            "Rendered code doesn't match",
        )
        self.assertEqual(
            rendered_command["rendered_path"],
            rendered_path_expected,
            "Rendered path doesn't match",
        )

        # -- 2 --
        # Test with custom path
        rendered_command = self.server_test_1._render_command(
            self.command_create_dir, path="/such/much/path"
        )
        rendered_code_expected = "cd /opt/tower && mkdir test-odoo-1"
        rendered_path_expected = "/such/much/path"

        self.assertEqual(
            rendered_command["rendered_code"],
            rendered_code_expected,
            "Rendered code doesn't match",
        )
        self.assertEqual(
            rendered_command["rendered_path"],
            rendered_path_expected,
            "Rendered path doesn't match",
        )

        # -- 3 --
        # Set variable_path to None and check again
        variable_value_path = self.server_test_1.variable_value_ids.filtered(
            lambda var_val: var_val.variable_id.id == self.variable_path.id
        )
        variable_value_path.value_char = None
        rendered_command = self.server_test_1._render_command(self.command_create_dir)
        rendered_code_expected = "cd False && mkdir test-odoo-1"
        rendered_path_expected = f"/home/{self.server_test_1.ssh_username}"

        self.assertEqual(
            rendered_command["rendered_code"],
            rendered_code_expected,
            "Rendered code doesn't match",
        )
        self.assertEqual(
            rendered_command["rendered_path"],
            rendered_path_expected,
            "Rendered path doesn't match",
        )

        # -- 4 --
        # Set both path and code to None
        self.write_and_invalidate(
            self.command_create_dir, **{"code": None, "path": None}
        )
        rendered_command = self.server_test_1._render_command(self.command_create_dir)

        self.assertFalse(
            rendered_command["rendered_code"], "Rendered code doesn't match"
        )
        self.assertFalse(
            rendered_command["rendered_path"], "Rendered path doesn't match"
        )

    def test_server_render_command_with_custom_variable_values(self):
        """Test rendering command using `_render_command` method
        of cx.tower.server with custom variable values
        """
        self.write_and_invalidate(
            self.server_test_1,
            **{"user_ids": [(4, self.user.id)], "manager_ids": [(4, self.manager.id)]},
        )
        # -- 1 --
        # Set custom variable values
        custom_variable_values = {
            "test_path_": "/pepe/memes",
            "other_path": "/etc/chad",
        }

        # Modify command path
        self.write_and_invalidate(
            self.command_create_dir,
            **{"path": "{{ other_path }}/{{ tower.server.username }}"},
        )

        # Render command
        rendered_command = self.server_test_1.with_user(self.manager)._render_command(
            self.command_create_dir, custom_variable_values=custom_variable_values
        )
        rendered_code_expected = "cd /pepe/memes && mkdir test-odoo-1"
        rendered_path_expected = f"/etc/chad/{self.server_test_1.ssh_username}"

        self.assertEqual(
            rendered_command["rendered_code"],
            rendered_code_expected,
            "Rendered code doesn't match",
        )
        self.assertEqual(
            rendered_command["rendered_path"],
            rendered_path_expected,
            "Rendered path doesn't match",
        )

        # -- 2 --
        # Test with user who doesn't have access to the server
        rendered_command = self.server_test_1.with_user(self.user)._render_command(
            self.command_create_dir, custom_variable_values=custom_variable_values
        )
        rendered_code_expected = "cd /opt/tower && mkdir test-odoo-1"
        rendered_path_expected = f"None/{self.server_test_1.ssh_username}"

        self.assertEqual(
            rendered_command["rendered_code"],
            rendered_code_expected,
            "Rendered code doesn't match",
        )
        self.assertEqual(
            rendered_command["rendered_path"],
            rendered_path_expected,
            "Rendered path doesn't match",
        )

    def test_server_render_command_variable_with_value_modifier(self):
        """Test rendering command using `_render_command` method
        of cx.tower.server.
        Use variable with value modifier for testing.
        """

        # -- 1 --
        # Set modifiers for variables
        modifier_for_path = """
if 'opt' in value:
    result = value.replace('opt', 'home')
else:
    result = value
"""
        self.variable_path.applied_expression = modifier_for_path

        modifier_for_dir = """
pattern = r'(?i)odoo'
replacement = 'sap'
result = re.sub(pattern, replacement, value)
"""
        self.variable_dir.applied_expression = modifier_for_dir

        # -- 1 --
        # Test with default path
        rendered_command = self.server_test_1._render_command(self.command_create_dir)
        rendered_code_expected = "cd /home/tower && mkdir test-sap-1"
        rendered_path_expected = f"/home/{self.server_test_1.ssh_username}"

        self.assertEqual(
            rendered_command["rendered_code"],
            rendered_code_expected,
            "Rendered code doesn't match",
        )
        self.assertEqual(
            rendered_command["rendered_path"],
            rendered_path_expected,
            "Rendered path doesn't match",
        )

        # -- 2 --
        # Set invalid expression modifier
        self.variable_path.applied_expression = "invalid"
        with mute_logger(
            "odoo.addons.cetmix_tower_server.models.cx_tower_variable_mixin"
        ):
            rendered_command = self.server_test_1._render_command(
                self.command_create_dir
            )
        rendered_code_expected = "cd /opt/tower && mkdir test-sap-1"
        rendered_path_expected = f"/home/{self.server_test_1.ssh_username}"

        self.assertEqual(
            rendered_command["rendered_code"],
            rendered_code_expected,
            "Rendered code doesn't match",
        )
        self.assertEqual(
            rendered_command["rendered_path"],
            rendered_path_expected,
            "Rendered path doesn't match",
        )

        # -- 3 --
        # Test with variable in variable value
        complex_variable = self.Variable.create(
            {
                "name": "Complex Variable",
                "applied_expression": "result = value.replace('opt', 'meme')",
            }
        )
        # Create a complex variable value
        self.VariableValue.create(
            {
                "variable_id": complex_variable.id,
                "value_char": "{{ test_path_ }}/{{ test_dir }}",
            }
        )
        command_with_complex_variable = self.Command.create(
            {
                "name": "Command with complex variable",
                "code": "cd {{ complex_variable }}",
                "action": "ssh_command",
            }
        )
        with mute_logger(
            "odoo.addons.cetmix_tower_server.models.cx_tower_variable_mixin"
        ):
            rendered_command = self.server_test_1._render_command(
                command_with_complex_variable
            )
        rendered_code_expected = "cd /meme/tower/test-sap-1"
        self.assertEqual(
            rendered_command["rendered_code"],
            rendered_code_expected,
            "Rendered code doesn't match",
        )

        # -- 4 --
        # Remove modifier from variable "Path" and check again
        self.variable_dir.applied_expression = None
        with mute_logger(
            "odoo.addons.cetmix_tower_server.models.cx_tower_variable_mixin"
        ):
            rendered_command = self.server_test_1._render_command(
                command_with_complex_variable
            )
        rendered_code_expected = "cd /meme/tower/test-odoo-1"

        self.assertEqual(
            rendered_command["rendered_code"],
            rendered_code_expected,
            "Rendered code doesn't match",
        )

    def test_render_code_generic(self):
        """Test generic (aka ssh) code template direct rendering"""

        # Only 'test_path_' must be rendered
        args = {"test_path_": "/tmp", "test_os": "debian"}
        res = self.command_create_dir.render_code(**args)
        rendered_code = res.get(self.command_create_dir.id)
        rendered_code_expected = "cd /tmp && mkdir "
        self.assertEqual(
            rendered_code,
            rendered_code_expected,
            msg=f"Must be rendered as '{rendered_code_expected}'",
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

    def test_run_command_with_variables(self):
        """Test code execution using command log records"""

        x = 1  # Used to distinguish labels

        # Check with all available "sudo" option
        for sudo in [False, "n", "p"]:
            # Add label to track command log
            self.server_test_1.use_sudo = sudo
            command_label = f"Test Command {x}"
            custom_values = {"log": {"label": command_label}}

            # Run command for Server 1
            self.server_test_1.run_command(
                self.command_create_dir, sudo=sudo, **custom_values
            )

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
                msg=f"Rendered code must be '{rendered_code_expected}'",
            )
            self.assertEqual(
                log_record.command_status, 0, msg="Command status must be equal to 0"
            )
            self.assertEqual(
                log_record.use_sudo,
                sudo,
                msg="'sudo' param in log doesn't match the command one",
            )

            # Increment label counter
            x += 1

    def test_run_command_with_keys(self):
        """Test command with keys in code"""

        # Command
        code = "cd {{ test_path_ }} && mkdir #!cxtower.secret.FOLDER!#"
        command_with_keys = self.Command.create(
            {"name": "Command with keys", "code": code}
        )

        # Parse command with key parser to ensure key is parsed correctly
        code_parsed_expected = "cd {{ test_path_ }} && mkdir secretFolder"
        code_parsed = self.Key._parse_code(code)
        self.assertEqual(
            code_parsed,
            code_parsed_expected,
            msg="Parsed code doesn't match expected one",
        )

        # Add label to track command log
        command_label = "Test Command with keys"
        custom_values = {"log": {"label": command_label}}

        # Run command for Server 1
        self.server_test_1.run_command(command_with_keys, **custom_values)

        # Expected rendered command code
        rendered_code_expected = "cd /opt/tower && mkdir #!cxtower.secret.FOLDER!#"

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
            msg=f"Rendered code must be '{rendered_code_expected}'",
        )
        self.assertEqual(
            log_record.command_status, 0, msg="Command status must be equal to 0"
        )

    def test_parse_ssh_command_result(self):
        """Test ssh command result parsing"""

        placeholder = self.Key.SECRET_VALUE_PLACEHOLDER
        # -------------------------------------------------------
        # Case 1: regular command execution result with no error
        # We are testing secret value placeholder here
        # -------------------------------------------------------
        status = 0
        response = ["Such much", f"Doge like SSH {placeholder}"]
        error = []

        ssh_command_result = self.Server._parse_command_results(
            status, response, error, key_values=[f"{self.secret_2.secret_value}"]
        )

        # Get result
        result_status = ssh_command_result["status"]
        result_response = ssh_command_result["response"]
        result_error = ssh_command_result["error"]

        self.assertEqual(
            result_status,
            status,
            "Status in result must be the same as the initial one",
        )
        self.assertEqual(
            result_response,
            f"Such muchDoge like SSH {placeholder}",
            "Response in result doesn't match expected",
        )
        self.assertIsNone(result_error, "Error in response must be set to None")

        # -------------------------------------------------------
        # Case 2: no response but an error
        # -------------------------------------------------------
        status = 1
        response = []
        error = ["Ooops", "I did", "it again"]

        ssh_command_result = self.Server._parse_command_results(status, response, error)

        # Get result
        result_status = ssh_command_result["status"]
        result_response = ssh_command_result["response"]
        result_error = ssh_command_result["error"]

        self.assertEqual(
            result_status,
            status,
            "Status in result must be the same as the initial one",
        )
        self.assertIsNone(result_response, "Response in response must be set to None")
        self.assertEqual(
            result_error, "OoopsI didit again", "Error in result doesn't match expected"
        )

        # -------------------------------------------------------
        # Case 3: several codes all 0, no response but an error
        # -------------------------------------------------------
        status = [0, 0, 0]
        response = []
        error = ["Ooops", "I did", "it again"]

        ssh_command_result = self.Server._parse_command_results(status, response, error)

        # Get result
        result_status = ssh_command_result["status"]
        result_response = ssh_command_result["response"]
        result_error = ssh_command_result["error"]

        self.assertEqual(
            result_status, 0, "Status in result doesn't match expected one"
        )
        self.assertIsNone(result_response, "Response in response must be set to None")
        self.assertEqual(
            result_error, "OoopsI didit again", "Error in result doesn't match expected"
        )

        # -------------------------------------------------------
        # Case 4: codes [0,1,0,4,0], no response but an error
        # -------------------------------------------------------
        status = [0, 1, 0, 4, 0]
        response = []
        error = ["Ooops", "I did", "it again"]

        ssh_command_result = self.Server._parse_command_results(status, response, error)

        # Get result
        result_status = ssh_command_result["status"]
        result_response = ssh_command_result["response"]
        result_error = ssh_command_result["error"]

        self.assertEqual(
            result_status, 4, "Status in result doesn't match expected one"
        )
        self.assertIsNone(result_response, "Response in response must be set to None")
        self.assertEqual(
            result_error, "OoopsI didit again", "Error in result doesn't match expected"
        )

        # -------------------------------------------------------
        # Case 5: regular command execution result with no error
        # However the command result is saved in the "error" value.
        # For example this happens in 'docker build'.
        # -------------------------------------------------------
        status = 0
        error = ["Such much", f"Doge like SSH {placeholder}"]
        response = []

        ssh_command_result = self.Server._parse_command_results(
            status, response, error, key_values=[f"{self.secret_2.secret_value}"]
        )

        # Get result
        result_status = ssh_command_result["status"]
        result_response = ssh_command_result["response"]
        result_error = ssh_command_result["error"]

        self.assertEqual(
            result_status,
            status,
            "Status in result must be the same as the initial one",
        )
        self.assertEqual(
            result_error,
            f"Such muchDoge like SSH {placeholder}",
            "Response in result doesn't match expected",
        )
        self.assertIsNone(result_response, "Error in response must be set to None")

    def test_tower_command_action_file_using_template(self):
        """
        Test action file using template for tower source
        """
        with patch(
            "odoo.addons.cetmix_tower_server.models.cx_tower_server.CxTowerServer.upload_file",
            return_value="ok",
        ):
            self.server_test_1.run_command(
                self.command_create_file_with_template_tower_source
            )

        log_text_create_success = "File created and uploaded successfully"
        log_text_file_exists = "An error occurred: File already exists on server."

        # Get command log
        log_record = self.CommandLog.search(
            [
                ("server_id", "=", self.server_test_1.id),
                (
                    "command_id",
                    "=",
                    self.command_create_file_with_template_tower_source.id,
                ),
                ("command_response", "=", log_text_create_success),
            ]
        )

        self.assertEqual(len(log_record), 1, msg="Must be a single log record")

        with patch(
            "odoo.addons.cetmix_tower_server.models.cx_tower_server.CxTowerServer.upload_file",
            return_value="ok",
        ):
            self.server_test_1.run_command(
                self.command_create_file_with_template_tower_source
            )

        log_record_2 = self.CommandLog.search(
            [
                ("server_id", "=", self.server_test_1.id),
                (
                    "command_id",
                    "=",
                    self.command_create_file_with_template_tower_source.id,
                ),
                ("command_error", "=", log_text_file_exists),
            ]
        )

        self.assertEqual(len(log_record_2), 1, msg="Must be a single log record")

    def test_server_command_action_file_using_template(self):
        """
        Test action file using template for server source
        """
        self.assertFalse(self.template_file_server.file_ids)

        def download_file(this, remote_path):
            return b"Hello, world!"

        cx_tower_server_obj = self.registry["cx.tower.server"]

        with patch.object(cx_tower_server_obj, "download_file", download_file):
            self.server_test_1.run_command(
                self.command_create_file_with_template_server_source
            )

        log_text_create_success = "File created and uploaded successfully"
        log_text_file_exists = "An error occurred: File already exists on server."

        # Get command log
        log_record = self.CommandLog.search(
            [
                ("server_id", "=", self.server_test_1.id),
                (
                    "command_id",
                    "=",
                    self.command_create_file_with_template_server_source.id,
                ),
                ("command_response", "=", log_text_create_success),
            ]
        )

        self.assertEqual(len(log_record), 1, msg="Must be a single log record")
        self.assertEqual(
            len(self.template_file_server.file_ids), 1, msg="Must be one file!"
        )
        self.assertEqual(
            self.template_file_server.file_ids.source,
            "server",
            msg="The File source must be 'server'",
        )

        with patch.object(cx_tower_server_obj, "download_file", download_file):
            self.server_test_1.run_command(
                self.command_create_file_with_template_server_source
            )

        log_record_2 = self.CommandLog.search(
            [
                ("server_id", "=", self.server_test_1.id),
                (
                    "command_id",
                    "=",
                    self.command_create_file_with_template_server_source.id,
                ),
                ("command_error", "=", log_text_file_exists),
            ]
        )

        self.assertEqual(len(log_record_2), 1, msg="Must be a single log record")

    def test_run_command_no_command_log(self):
        """Run command without creating a log record.
        Such commands return execution result directly.
        """
        # Add label to track command log
        command_label = "Test Command with keys"
        custom_values = {"log": {"label": command_label}}

        # Run command for Server 1
        command_result = self.server_test_1.with_context(
            no_command_log=True
        ).run_command(self.command_create_dir, **custom_values)
        self.assertEqual(
            command_result["status"], 0, "Command status doesn't match expected one"
        )
        self.assertEqual(
            command_result["response"],
            "ok",
            "Command response doesn't match expected one",
        )
        self.assertIsNone(
            command_result["error"], "Command error doesn't match expected one"
        )

    def test_another_command_is_running(self):
        """Test a case when another command is running on the same server"""

        # Remove all existing command logs
        self.CommandLog.search([]).unlink()

        # Create a new command log
        initial_command_log = self.CommandLog.create(
            {
                "server_id": self.server_test_1.id,
                "command_id": self.command_create_new_command.id,
                "start_date": Datetime.now(),
            }
        )

        # Run the command without creating a log record
        command_result = self.server_test_1.with_context(
            no_command_log=True
        ).run_command(self.command_create_new_command)
        self.assertEqual(command_result["status"], ANOTHER_COMMAND_RUNNING)

        # Run the command with creating a log record
        command_result = self.server_test_1.run_command(self.command_create_new_command)

        # Get the command log
        command_log = self.CommandLog.search(
            [
                ("server_id", "=", self.server_test_1.id),
                ("command_id", "=", self.command_create_new_command.id),
                ("id", "!=", initial_command_log.id),
            ]
        )
        self.assertEqual(len(command_log), 1, "Must be a single log record")
        self.assertEqual(command_log.command_status, ANOTHER_COMMAND_RUNNING)

    def test_file_using_template_create_if_exists(self):
        """Test uploading file using template if it exists on server."""

        command = self.command_create_file_with_template_server_source
        command.write({"if_file_exists": "skip"})

        # Create file to make sure that it exists on the server
        file_template = command.file_template_id
        orig_file = file_template.create_file(
            server=self.server_test_1,
            server_dir=file_template.server_dir,
            if_file_exists=command.if_file_exists,
        )

        self.assertTrue(orig_file, "File must be created on the server")

        # Test if file exists and command is set to "skip"
        skipped_file = file_template.create_file(
            server=self.server_test_1,
            server_dir=file_template.server_dir,
            if_file_exists=command.if_file_exists,
        )
        self.assertEqual(
            orig_file,
            skipped_file,
            "Skip should return the existing file, not create a new one",
        )
        self.assertEqual(
            self.env["cx.tower.file"].search_count(
                [
                    ("template_id", "=", file_template.id),
                    ("server_id", "=", self.server_test_1.id),
                ]
            ),
            1,
            "There must be exactly one physical file record after skip",
        )

        # Change command to raise an error if file exists
        command.write({"if_file_exists": "raise"})
        with self.assertRaisesRegex(
            ValidationError,
            "File already exists on server.",
        ):
            file_template.create_file(
                server=self.server_test_1,
                server_dir=file_template.server_dir,
                if_file_exists=command.if_file_exists,
            )
        # Change command to "overwrite" file if it exists
        command.write({"if_file_exists": "overwrite"})
        # Run command again, it should overwrite the file
        file_template.create_file(
            server=self.server_test_1,
            server_dir=file_template.server_dir,
            if_file_exists=command.if_file_exists,
        )
        self.assertEqual(
            self.env["cx.tower.file"].search_count(
                [
                    ("template_id", "=", file_template.id),
                    ("server_id", "=", self.server_test_1.id),
                    ("server_dir", "=", file_template.server_dir),
                ]
            ),
            1,
            "There must be exactly one physical file record after overwrite",
        )
        self.assertEqual(
            orig_file.code,
            file_template.code,
            "File code must match template after overwrite",
        )
        self.assertEqual(
            orig_file.name,
            file_template.file_name,
            "File name must match template after overwrite",
        )
        self.assertEqual(
            orig_file.source,
            file_template.source,
            "File source must match template after overwrite",
        )

    def test_is_file_disconnected_from_template(self):
        """Test if file is disconnected from template after being created."""

        initial_files = self.server_test_1.file_ids
        command = self.command_create_file_with_template_server_source

        command.disconnect_file = True
        self.server_test_1.run_command(command=command)

        new_files = self.server_test_1.file_ids - initial_files
        self.assertEqual(len(new_files), 1, "Must be one new file created")
        self.assertEqual(
            new_files.code_on_server,
            command.file_template_id.code,
            "File code must match template",
        )
        self.assertFalse(
            new_files.template_id, "File must be disconnected from template"
        )

    # ---------------------
    # *********************
    #   Python commands
    # *********************
    # ---------------------

    def test_render_code_python(self):
        """Test Python code template direct rendering"""

        rendered_command = self.server_test_1._render_command(
            self.command_create_new_command
        )

        # Note: this is rendered as for Server Test 1
        rendered_code_pythonic = (
            f"""
server_name = "{self.server_test_1.name}"
if server_name and #!cxtower.secret.FOLDER!# == "secretFolder":
    # We don't actually create a new command because it will raise
    # access error if user doesn't have access to 'create' operation.
    # Instead we just return a dummy command result.
    command = "new command"
    result = {{"exit_code": 0, "message": "New command was created"}}
else:
    result = {{"exit_code": %s, "message": "error"}}
    """
            % GENERAL_ERROR
        )

        self.assertEqual(
            rendered_command["rendered_code"],
            rendered_code_pythonic,
            "Rendered code doesn't match",
        )

    def test_execute_python_command(self):
        """
        Run command with python action.
        """
        command_result = self.server_test_1.with_context(
            no_command_log=True
        ).run_command(self.command_create_new_command)
        self.assertEqual(
            command_result["status"], 0, "The command result status must be 0"
        )
        self.assertEqual(
            command_result["response"],
            "New command was created",
            "The response must be text",
        )

        # Check error is raises
        self.secret_folder_key.secret_value = "not_a_secretFolder"
        command_result = self.server_test_1.with_context(
            no_command_log=True
        ).run_command(self.command_create_new_command)
        self.assertEqual(
            command_result["status"],
            GENERAL_ERROR,
            "The command result status must be GENERAL_ERROR",
        )
        self.assertEqual(
            command_result["error"],
            "error",
            "The error response must be contain text - error",
        )

    def test_run_python_code(self):
        """
        Test python execution code
        """
        rendered_command = self.server_test_1._render_command(
            self.command_create_new_command
        )

        command_result = self.server_test_1._run_python_code(
            rendered_command["rendered_code"]
        )
        self.assertEqual(
            command_result["status"], 0, "The command result status must be 0"
        )
        self.assertEqual(
            command_result["response"],
            "New command was created",
            "The response must be text",
        )
        self.assertIsNone(
            command_result["error"],
            "Error in command result must be set to None",
        )

    def test_run_command_without_set_server_status(self):
        """
        Test command execution without setting server status
        """
        # Set command access level to "user"
        self.command_create_new_command.write({"access_level": "1"})

        # Add user to command
        self.write_and_invalidate(
            self.server_test_1, **{"user_ids": [(4, self.user.id)]}
        )

        # Reset access rule cache
        self.env["ir.rule"].invalidate_recordset()

        # Run command
        server_status = self.server_test_1.status

        result = (
            self.server_test_1.with_context(no_command_log=True)
            .with_user(self.user)
            .run_command(self.command_create_new_command)
        )

        # Check command result
        self.assertEqual(result["status"], 0, "Command status must be 0")
        self.assertEqual(
            self.server_test_1.status, server_status, "Server status must be 'running'"
        )

    def test_run_command_with_set_server_status(self):
        """
        Test command execution with setting server status
        """
        # Set server status to "down"
        self.command_create_new_command.write({"server_status": "stopping"})

        # Run command
        self.server_test_1.with_context(no_command_log=True).run_command(
            self.command_create_new_command
        )

        # Check command result
        self.assertEqual(
            self.server_test_1.status, "stopping", "Server status must be 'stopping'"
        )

    def test_run_python_code_with_secret(self):
        """
        Test execution of Python code with a secret value.
        This test ensures that a command is rendered and executed correctly,
        and that the secret value is correctly handled and replaced in the output.
        """

        placeholder = self.Key.SECRET_VALUE_PLACEHOLDER
        # Case 1
        # Render the command using server_test_1
        rendered_command = self.server_test_1._render_command(
            self.command_python_command_1
        )

        # Run the rendered Python code
        command_result = self.server_test_1._run_python_code(
            rendered_command["rendered_code"]
        )

        # Assert that the command execution status is 0 (indicating success)
        self.assertEqual(
            command_result["status"], 0, "The command result status must be 0"
        )

        # Assert that the response contains the secret spoiler text
        self.assertEqual(
            command_result["response"],
            placeholder,
            "The response must correctly include the secret value placeholder",
        )

        # Assert that no error occurred during execution (error should be None)
        self.assertIsNone(
            command_result["error"],
            "The error in command result must be None",
        )

        # Case 2
        # Render the command using server_test_1
        rendered_command = self.server_test_1._render_command(
            self.command_python_command_2
        )

        # Run the rendered Python code
        command_result = self.server_test_1._run_python_code(
            rendered_command["rendered_code"]
        )

        # Assert that the command execution status is 0 (indicating success)
        self.assertEqual(
            command_result["status"], 0, "The command result status must be 0"
        )

        # Assert that the response contains the secret spoiler text
        self.assertEqual(
            command_result["response"],
            f'We use "{placeholder}"',
            "The response must correctly include the secret value placeholder",
        )

        # Assert that no error occurred during execution (error should be None)
        self.assertIsNone(
            command_result["error"],
            "The error in command result must be None",
        )

        # Case 3
        # Render the command using server_test_1
        rendered_command = self.server_test_1._render_command(
            self.command_python_command_3
        )

        # Run the rendered Python code
        command_result = self.server_test_1._run_python_code(
            rendered_command["rendered_code"]
        )

        # Assert that the command execution status is 0 (indicating success)
        self.assertEqual(
            command_result["status"], 0, "The command result status must be 0"
        )

        # Assert that the response contains the secret spoiler text
        self.assertEqual(
            command_result["response"],
            placeholder,
            "The response must correctly include the secret value placeholder",
        )

        # Assert that no error occurred during execution (error should be None)
        self.assertIsNone(
            command_result["error"],
            "The error in command result must be None",
        )

        # Case 4
        # Render the command using server_test_1
        rendered_command = self.server_test_1._render_command(
            self.command_python_command_4
        )

        # Run the rendered Python code
        # SSH keys are not parsed inline, so the command returns a successful
        # placeholder response
        command_result = self.server_test_1._run_python_code(
            rendered_command["rendered_code"]
        )

        # Assert that the command execution status is 0 (indicating success)
        self.assertEqual(
            command_result["status"], 0, "The command result status must be 0"
        )

        # Assert that the response contains the secret spoiler text
        self.assertEqual(
            command_result["response"],
            placeholder,
            "The response must correctly include the secret value placeholder",
        )

        # Assert that no error occurred during execution (error should be None)
        self.assertIsNone(
            command_result["error"],
            "The error in command result must be None",
        )

    def test_command_with_secret(self):
        """
        Test case to verify that when a command includes a secret reference,
        the secret key is automatically linked with the command.
        """

        # Command with a secret reference
        code = "cd {{ test_path_ }} && mkdir #!cxtower.secret.FOLDER!#"

        secrets = self.Command._extract_secret_ids(code)
        secret_folder_key = self.secret_folder_key
        self.assertIn(
            secret_folder_key,
            secrets,
            msg=(
                f"The expected secret ID #{secret_folder_key.id} "
                "was not found in the provided code."
            ),
        )

        command_with_keys = self.Command.create(
            {"name": "Command with keys", "code": code}
        )

        # -- 1 --
        # Assert that the secret key is linked with the command
        self.assertIn(
            secret_folder_key,
            command_with_keys.secret_ids,
            msg="The secret key is not linked with the command.",
        )

        # -- 2 --
        #  Update the command's code to remove the secret reference
        updated_code = "cd {{ test_path_ }} && mkdir new_folder"
        command_with_keys.code = updated_code

        self.assertFalse(
            command_with_keys.secret_ids,
            msg=(
                "The secret_ids field should be empty after "
                "removing the secret reference from command."
            ),
        )

        # -- 3 --
        # Create a secret with the same reference but connected to another server
        another_server = self.server_test_1.copy({"name": "another server"})
        another_secret = self.Key.create(
            {
                "name": "another secret",
                "reference": secret_folder_key.reference,
                "key_type": "s",
            }
        )
        another_secret_value = self.KeyValue.create(
            {
                "key_id": another_secret.id,
                "server_id": another_server.id,
                "secret_value": "another secret value",
            }
        )
        # Set original code again
        command_with_keys.code = code
        self.assertEqual(
            len(command_with_keys.secret_ids),
            1,
            msg="Must be only one secret",
        )
        self.assertIn(
            secret_folder_key,
            command_with_keys.secret_ids,
            msg="The secret key is not linked with the command.",
        )
        self.assertNotIn(
            another_secret,
            command_with_keys.secret_ids,
            msg="The another secret is linked with the command.",
        )

        # -- 4 --
        # Connect command to server and secret to another server
        # and ensure it's unlinked from the command.
        yet_one_more_server = self.server_test_1.copy({"name": "yet one more server"})

        self.write_and_invalidate(
            another_secret_value, **{"server_id": yet_one_more_server.id}
        )
        self.write_and_invalidate(
            command_with_keys, **{"server_ids": self.server_test_1}
        )
        self.assertEqual(
            len(command_with_keys.secret_ids),
            1,
            msg="Must be one secret",
        )

    def test_check_zombie_commands(self):
        """Test checking and marking zombie commands"""
        # Create test commands
        ssh_command = self.Command.create(
            {
                "name": "Test SSH Command",
                "code": "ls -la",
                "action": "ssh_command",
            }
        )
        python_command = self.Command.create(
            {
                "name": "Test Python Command",
                "code": "print('test')",
                "action": "python_code",
            }
        )
        plan_command = self.Command.create(
            {
                "name": "Test Plan Command",
                "code": "test plan",
                "action": "plan",
            }
        )

        # Set command timeout to 10 seconds
        self.env["ir.config_parameter"].sudo().set_param(
            "cetmix_tower_server.command_timeout", "10"
        )

        # Create command logs with different start times
        now = Datetime.now()
        old_time = now - timedelta(seconds=20)  # Older than timeout
        recent_time = now - timedelta(seconds=5)  # Within timeout

        # Create zombie SSH command log
        zombie_ssh_log = self.CommandLog.create(
            {
                "command_id": ssh_command.id,
                "server_id": self.server_test_1.id,
                "start_date": old_time,
            }
        )

        # Create zombie Python command log
        zombie_python_log = self.CommandLog.create(
            {
                "command_id": python_command.id,
                "server_id": self.server_test_1.id,
                "start_date": old_time,
            }
        )

        # Create non-zombie command logs
        active_ssh_log = self.CommandLog.create(
            {
                "command_id": ssh_command.id,
                "server_id": self.server_test_1.id,
                "start_date": recent_time,
            }
        )

        plan_log = self.CommandLog.create(
            {
                "command_id": plan_command.id,
                "server_id": self.server_test_1.id,
                "start_date": old_time,
            }
        )

        # Test with timeout set
        self.server_test_1._check_zombie_commands()

        # Check zombie commands are marked as finished
        self.assertFalse(
            zombie_ssh_log.is_running, "Zombie SSH command should be marked as finished"
        )
        self.assertFalse(
            zombie_python_log.is_running,
            "Zombie Python command should be marked as finished",
        )
        self.assertEqual(
            zombie_ssh_log.command_status,
            COMMAND_TIMED_OUT,
            "Zombie SSH command should have timed out status",
        )
        self.assertEqual(
            zombie_python_log.command_error,
            COMMAND_TIMED_OUT_MESSAGE,
            "Zombie Python command should have timeout error message",
        )

        # Check non-zombie commands are still running
        self.assertTrue(
            active_ssh_log.is_running, "Recent command should still be running"
        )
        self.assertTrue(
            plan_log.is_running, "Plan command should not be affected by timeout"
        )

        # Test with timeout disabled
        self.env["ir.config_parameter"].sudo().set_param(
            "cetmix_tower_server.command_timeout", "0"
        )

        # Create new zombie command log
        new_zombie_log = self.CommandLog.create(
            {
                "command_id": ssh_command.id,
                "server_id": self.server_test_1.id,
                "start_date": old_time,
            }
        )

        self.server_test_1._check_zombie_commands()
        self.assertNotEqual(
            new_zombie_log.command_status,
            COMMAND_TIMED_OUT,
            "Commands should not be marked as timed out when timeout is disabled",
        )

    def test_command_with_malformed_code(self):
        """Test rendering command using `_render_command` method
        of cx.tower.server with malformed code
        """

        with self.assertRaises(ValidationError):
            self.Command.create(
                {
                    "name": "Test Malformed Command",
                    "code": "cd {{ !@238203 }} && mkdir #!cxtower.secret.FOLDER!#",
                    "action": "ssh_command",
                }
            )
