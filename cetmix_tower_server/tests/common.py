# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import os
from unittest.mock import MagicMock, patch

from odoo import _
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase

from odoo.addons.cetmix_tower_server.models.cx_tower_server import SSH


class TestTowerCommon(TransactionCase):
    def setUp(self, *args, **kwargs):
        super().setUp(*args, **kwargs)
        # ***
        # Create core elements invoked in the tests
        # ***

        # Cetmix Tower helper model
        self.CetmixTower = self.env["cetmix.tower"]

        # Tags
        self.Tag = self.env["cx.tower.tag"]
        self.tag_test_staging = self.Tag.create({"name": "Test Staging"})
        self.tag_test_production = self.Tag.create({"name": "Test Production"})

        # Users
        self.Users = self.env["res.users"].with_context(no_reset_password=True)
        self.user_bob = self.Users.create(
            {
                "name": "Bob",
                "login": "bob",
                "groups_id": [(4, self.env.ref("base.group_user").id)],
            }
        )

        # OS
        self.os_debian_10 = self.env["cx.tower.os"].create({"name": "Test Debian 10"})

        # Server
        self.Server = self.env["cx.tower.server"]
        self.server_test_1 = self.Server.create(
            {
                "name": "Test 1",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "os_id": self.os_debian_10.id,
            }
        )

        # Server Template
        self.ServerTemplate = self.env["cx.tower.server.template"]
        self.server_template_sample = self.ServerTemplate.create(
            {
                "name": "Sample Template",
                "ssh_port": 22,
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "os_id": self.os_debian_10.id,
            }
        )

        # Server log
        self.ServerLog = self.env["cx.tower.server.log"]

        # Variable
        self.Variable = self.env["cx.tower.variable"]
        self.VariableValue = self.env["cx.tower.variable.value"]
        self.VariableOption = self.env["cx.tower.variable.option"]

        self.variable_path = self.Variable.create({"name": "test_path_"})
        self.variable_dir = self.Variable.create({"name": "test_dir"})
        self.variable_os = self.Variable.create({"name": "test_os"})
        self.variable_url = self.Variable.create({"name": "test_url"})
        self.variable_version = self.Variable.create({"name": "test_version"})

        # Key
        self.Key = self.env["cx.tower.key"]

        self.key_1 = self.Key.create(
            {"name": "Test Key 1", "key_type": "k", "secret_value": "much key"}
        )
        self.secret_2 = self.Key.create(
            {"name": "Test Key 2", "key_type": "s", "secret_value": "secret top"}
        )

        # Command
        self.sudo_prefix = "sudo -S -p ''"
        self.Command = self.env["cx.tower.command"]
        self.command_create_dir = self.Command.create(
            {
                "name": "Test create directory",
                "path": "/home/{{ tower.server.username }}",
                "code": "cd {{ test_path_ }} && mkdir {{ test_dir }}",
            }
        )
        self.command_list_dir = self.Command.create(
            {
                "name": "Test create directory",
                "path": "/home/{{ tower.server.username }}",
                "code": "cd {{ test_path_ }} && ls -l",
            }
        )

        self.template_file_tower = self.env["cx.tower.file.template"].create(
            {
                "name": "Test file template",
                "file_name": "test_os.txt",
                "source": "tower",
                "server_dir": "/home/{{ tower.server.username }}",
                "code": "Hello, world!",
            }
        )

        self.template_file_server = self.env["cx.tower.file.template"].create(
            {
                "name": "Test file template",
                "file_name": "test_os.txt",
                "source": "server",
                "server_dir": "/home/{{ tower.server.username }}",
            }
        )

        self.command_create_file_with_template_tower_source = self.Command.create(
            {
                "name": "Test create file with template with tower source",
                "path": "/home/{{ tower.server.username }}",
                "action": "file_using_template",
                "file_template_id": self.template_file_tower.id,
            }
        )

        self.command_create_file_with_template_server_source = self.Command.create(
            {
                "name": "Test create file with template with server source",
                "path": "/home/{{ tower.server.username }}",
                "action": "file_using_template",
                "file_template_id": self.template_file_server.id,
            }
        )

        # Command log
        self.CommandLog = self.env["cx.tower.command.log"]

        # File template
        self.FileTemplate = self.env["cx.tower.file.template"]

        # File
        self.File = self.env["cx.tower.file"]

        # Flight Plans
        self.Plan = self.env["cx.tower.plan"]
        self.plan_line = self.env["cx.tower.plan.line"]
        self.plan_line_action = self.env["cx.tower.plan.line.action"]

        self.plan_1 = self.Plan.create(
            {
                "name": "Test plan 1",
                "note": "Create directory and list its content",
                "tag_ids": [(6, 0, [self.tag_test_staging.id])],
            }
        )
        self.plan_line_1 = self.plan_line.create(
            {
                "sequence": 5,
                "plan_id": self.plan_1.id,
                "command_id": self.command_create_dir.id,
                "path": "/such/much/path",
            }
        )
        self.plan_line_2 = self.plan_line.create(
            {
                "sequence": 20,
                "plan_id": self.plan_1.id,
                "command_id": self.command_list_dir.id,
            }
        )
        self.plan_line_1_action_1 = self.plan_line_action.create(
            {
                "line_id": self.plan_line_1.id,
                "sequence": 1,
                "condition": "==",
                "value_char": "0",
            }
        )
        self.plan_line_1_action_2 = self.plan_line_action.create(
            {
                "line_id": self.plan_line_1.id,
                "sequence": 2,
                "condition": ">",
                "value_char": "0",
                "action": "ec",
                "custom_exit_code": 255,
            }
        )
        self.plan_line_2_action_1 = self.plan_line_action.create(
            {
                "line_id": self.plan_line_2.id,
                "sequence": 1,
                "condition": "==",
                "value_char": "-1",
                "action": "ec",
                "custom_exit_code": 100,
            }
        )
        self.plan_line_2_action_2 = self.plan_line_action.create(
            {
                "line_id": self.plan_line_2.id,
                "sequence": 2,
                "condition": ">=",
                "value_char": "3",
                "action": "n",
            }
        )

        # Flight plan log
        self.PlanLog = self.env["cx.tower.plan.log"]

        # apply ssh connection patches
        self.apply_patches()

    def apply_patches(self):
        """
        Apply mock patches for SSH-related methods to simulate various scenarios
        during testing.

        This method sets up and applies the following mock patches:

        1. `_connect` method:
            - Returns a mocked SSH connection object that simulates the behavior of an
              SSH connection.
            - The `exec_command` method is patched to return:
                - `stdin`: A `MagicMock` instance.
                - `stdout`: A mocked object where:
                    - `channel.recv_exit_status` returns:
                        - `0` for successful commands.
                        - `-1` for commands that simulate a failure
                          (e.g., commands containing the string `"fail"`).
                    - `readlines` returns:
                        - `["ok"]` for successful commands.
                        - An empty list for failed commands.
                - `stderr`: A mocked object where:
                    - `readlines` returns:
                        - `["error"]` for failed commands.
                        - An empty list for successful commands.

        2. `download_file` method:
            - Simulates the behavior of downloading a file and returns:
                - A binary string `b"ok\x00"` for files with the `.zip` extension.
                - A binary string `b"ok"` for files with all other extensions.

        3. `upload_file` method:
            - Returns a `MagicMock` object to simulate file upload behavior without
              actual execution.

        4. `delete_file` method:
            - Returns a `MagicMock` object to simulate file deletion behavior without
              actual execution.

        The patches are applied immediately using `patch.object` and are added to
        `addCleanup` to ensure they are automatically stopped after the tests are
        executed.

        This method should be called during the test setup phase to mock the required
        behaviors.
        """

        # Patch connection SSH method
        def ssh_connect(self):
            connection_mock = MagicMock()

            # set up stdin with a condition for error simulation
            def exec_command_side_effect(command, *args, **kwargs):
                # Create mocks for stdin, stdout, and stderr
                stdin_mock = MagicMock()
                stdout_mock = MagicMock()
                stderr_mock = MagicMock()

                if "fail" in command:
                    # Simulate failure
                    stdout_mock.channel.recv_exit_status.return_value = -1
                    stdout_mock.readlines.return_value = []
                    stderr_mock.readlines.return_value = ["error"]
                    return stdin_mock, stdout_mock, stderr_mock
                else:
                    # Simulate success
                    stdout_mock.channel.recv_exit_status.return_value = 0
                    stdout_mock.readlines.return_value = ["ok"]
                    stderr_mock.readlines.return_value = []
                    return stdin_mock, stdout_mock, stderr_mock

            # Apply side effect to exec_command
            connection_mock.exec_command.side_effect = exec_command_side_effect

            return connection_mock

        connect_patch = patch.object(SSH, "_connect", ssh_connect)
        connect_patch.start()
        self.addCleanup(connect_patch.stop)

        # Patch file manipulation methods for testing
        def ssh_download_file(self, remote_path):
            _, extension = os.path.splitext(remote_path)
            if extension == ".zip":
                return b"ok\x00"
            return b"ok"

        download_file_patch = patch.object(SSH, "download_file", ssh_download_file)
        download_file_patch.start()
        self.addCleanup(download_file_patch.stop)

        def ssh_upload_file(self, file, remote_path):
            return MagicMock()

        upload_file_patch = patch.object(SSH, "upload_file", ssh_upload_file)
        upload_file_patch.start()
        self.addCleanup(upload_file_patch.stop)

        def ssh_delete_file(self, remote_path):
            return MagicMock()

        delete_file_patch = patch.object(SSH, "delete_file", ssh_delete_file)
        delete_file_patch.start()
        self.addCleanup(delete_file_patch.stop)

    def add_to_group(self, user, group_refs):
        """Add user to groups

        Args:
            user (res.users): User record
            group_refs (list): Group ref OR List of group references
                eg ['base.group_user', 'some_module.some_group'...]
        """
        if isinstance(group_refs, str):
            action = [(4, self.env.ref(group_refs).id)]
        elif isinstance(group_refs, list):
            action = [(4, self.env.ref(group_ref).id) for group_ref in group_refs]
        else:
            raise ValidationError(_("groups_ref must be string or list of strings!"))
        user.write({"groups_id": action})

    def remove_from_group(self, user, group_refs):
        """Remove user from groups

        Args:
            user (res.users): User record
            group_refs (list): List of group references
                eg ['base.group_user', 'some_module.some_group'...]
        """
        if isinstance(group_refs, str):
            action = [(3, self.env.ref(group_refs).id)]
        elif isinstance(group_refs, list):
            action = [(3, self.env.ref(group_ref).id) for group_ref in group_refs]
        else:
            raise ValidationError(_("groups_ref must be string or list of strings!"))
        user.write({"groups_id": action})

    def write_and_invalidate(self, records, **values):
        """Write values and invalidate cache

        Args:
            records (recordset): recordset to save values
            **values (dict): values to set
        """
        if values:
            records.write(values)
            records.invalidate_cache(values.keys())
