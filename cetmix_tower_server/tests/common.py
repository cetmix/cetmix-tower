# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import os
from unittest.mock import MagicMock, patch

from odoo import _
from odoo.exceptions import ValidationError

from odoo.addons.base.tests.common import BaseCommon

from ..models.constants import GENERAL_ERROR
from ..ssh.ssh import SftpService, SSHConnection


class TestTowerCommon(BaseCommon):
    """
    Common test class for Cetmix Tower.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ----------------------------------------------
        # -- Create core elements invoked in the tests
        # ----------------------------------------------
        # Group XML records
        cls.group_user = cls.env.ref("cetmix_tower_server.group_user")
        cls.group_manager = cls.env.ref("cetmix_tower_server.group_manager")
        cls.group_root = cls.env.ref("cetmix_tower_server.group_root")

        # Cetmix Tower helper model
        cls.CetmixTower = cls.env["cetmix.tower"]

        # Tags
        cls.Tag = cls.env["cx.tower.tag"]
        cls.tag_test_staging = cls.Tag.create({"name": "Test Staging"})
        cls.tag_test_production = cls.Tag.create({"name": "Test Production"})

        # Users
        cls.Users = cls.env["res.users"]
        cls.user_bob = cls.Users.create(
            {
                "name": "Bob",
                "login": "bob",
                "groups_id": [(4, cls.env.ref("base.group_user").id)],
            }
        )
        cls.user = cls.Users.create(
            {
                "name": "Test User",
                "login": "test_user",
                "email": "test_user@example.com",
                "groups_id": [
                    (6, 0, [cls.group_user.id, cls.env.ref("base.group_user").id])
                ],
            }
        )
        cls.manager = cls.Users.create(
            {
                "name": "Test Manager",
                "login": "test_manager",
                "email": "test_manager@example.com",
                "groups_id": [
                    (6, 0, [cls.group_manager.id, cls.env.ref("base.group_user").id])
                ],
            }
        )
        cls.root = cls.Users.create(
            {
                "name": "Test Root",
                "login": "test_root",
                "email": "test_root@example.com",
                "groups_id": [
                    (6, 0, [cls.group_root.id, cls.env.ref("base.group_user").id])
                ],
            }
        )

        # OS
        cls.os_debian_10 = cls.env["cx.tower.os"].create({"name": "Test Debian 10"})

        # Server
        cls.Server = cls.env["cx.tower.server"]
        cls.server_test_1 = cls.Server.create(
            {
                "name": "Test 1",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "host_key": "test_key",
                "os_id": cls.os_debian_10.id,
            }
        )

        # Server Template
        cls.ServerTemplate = cls.env["cx.tower.server.template"]
        cls.server_template_sample = cls.ServerTemplate.create(
            {
                "name": "Sample Template",
                "ssh_port": 22,
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "os_id": cls.os_debian_10.id,
            }
        )

        # Server log
        cls.ServerLog = cls.env["cx.tower.server.log"]

        # Variable
        cls.Variable = cls.env["cx.tower.variable"]
        cls.VariableValue = cls.env["cx.tower.variable.value"]
        cls.VariableOption = cls.env["cx.tower.variable.option"]

        cls.variable_path = cls.Variable.create({"name": "test_path_"})
        cls.variable_dir = cls.Variable.create({"name": "test_dir"})
        cls.variable_os = cls.Variable.create({"name": "test_os"})
        cls.variable_url = cls.Variable.create({"name": "test_url"})
        cls.variable_version = cls.Variable.create({"name": "test_version"})

        # Key
        cls.Key = cls.env["cx.tower.key"]
        cls.KeyValue = cls.env["cx.tower.key.value"]

        cls.key_1 = cls.Key.create(
            {"name": "Test Key 1", "key_type": "k", "secret_value": "much key"}
        )
        cls.secret_2 = cls.Key.create(
            {"name": "Test Key 2", "key_type": "s", "secret_value": "secret top"}
        )

        # Command
        cls.sudo_prefix = "sudo -S -p ''"
        cls.Command = cls.env["cx.tower.command"]
        cls.command_create_dir = cls.Command.create(
            {
                "name": "Test create directory",
                "path": "/home/{{ tower.server.username }}",
                "code": "cd {{ test_path_ }} && mkdir {{ test_dir }}",
            }
        )
        cls.command_list_dir = cls.Command.create(
            {
                "name": "Test create directory",
                "path": "/home/{{ tower.server.username }}",
                "code": "cd {{ test_path_ }} && ls -l",
            }
        )

        cls.template_file_tower = cls.env["cx.tower.file.template"].create(
            {
                "name": "Test file template",
                "file_name": "test_os.txt",
                "source": "tower",
                "server_dir": "/home/{{ tower.server.username }}",
                "code": "Hello, world!",
            }
        )

        cls.template_file_server = cls.env["cx.tower.file.template"].create(
            {
                "name": "Test file template",
                "file_name": "test_os.txt",
                "source": "server",
                "server_dir": "/home/{{ tower.server.username }}",
            }
        )

        cls.command_create_file_with_template_tower_source = cls.Command.create(
            {
                "name": "Test create file with template with tower source",
                "path": "/home/{{ tower.server.username }}",
                "action": "file_using_template",
                "file_template_id": cls.template_file_tower.id,
                "if_file_exists": "raise",
            }
        )

        cls.command_create_file_with_template_server_source = cls.Command.create(
            {
                "name": "Test create file with template with server source",
                "path": "/home/{{ tower.server.username }}",
                "action": "file_using_template",
                "file_template_id": cls.template_file_server.id,
                "if_file_exists": "raise",
            }
        )

        # Command log
        cls.CommandLog = cls.env["cx.tower.command.log"]

        # File template
        cls.FileTemplate = cls.env["cx.tower.file.template"]

        # File
        cls.File = cls.env["cx.tower.file"]

        # Flight Plans
        cls.Plan = cls.env["cx.tower.plan"]
        cls.plan_line = cls.env["cx.tower.plan.line"]
        cls.plan_line_action = cls.env["cx.tower.plan.line.action"]

        cls.plan_1 = cls.Plan.create(
            {
                "name": "Test plan 1",
                "note": "Create directory and list its content",
                "tag_ids": [(6, 0, [cls.tag_test_staging.id])],
            }
        )
        cls.plan_line_1 = cls.plan_line.create(
            {
                "sequence": 5,
                "plan_id": cls.plan_1.id,
                "command_id": cls.command_create_dir.id,
                "path": "/such/much/path",
            }
        )
        cls.plan_line_2 = cls.plan_line.create(
            {
                "sequence": 20,
                "plan_id": cls.plan_1.id,
                "command_id": cls.command_list_dir.id,
            }
        )
        cls.plan_line_1_action_1 = cls.plan_line_action.create(
            {
                "line_id": cls.plan_line_1.id,
                "sequence": 1,
                "condition": "==",
                "value_char": "0",
            }
        )
        cls.plan_line_1_action_2 = cls.plan_line_action.create(
            {
                "line_id": cls.plan_line_1.id,
                "sequence": 2,
                "condition": ">",
                "value_char": "0",
                "action": "ec",
                "custom_exit_code": 255,
            }
        )
        cls.plan_line_2_action_1 = cls.plan_line_action.create(
            {
                "line_id": cls.plan_line_2.id,
                "sequence": 1,
                "condition": "==",
                "value_char": "-1",
                "action": "ec",
                "custom_exit_code": 100,
            }
        )
        cls.plan_line_2_action_2 = cls.plan_line_action.create(
            {
                "line_id": cls.plan_line_2.id,
                "sequence": 2,
                "condition": ">=",
                "value_char": "3",
                "action": "n",
            }
        )

        # Flight plan log
        cls.PlanLog = cls.env["cx.tower.plan.log"]

        # Shortcut
        cls.Shortcut = cls.env["cx.tower.shortcut"]

        # Model references
        cls.OS = cls.env["cx.tower.os"]
        cls.PlanLineAction = cls.env["cx.tower.plan.line.action"]

        # Scheduled task
        cls.ScheduledTask = cls.env["cx.tower.scheduled.task"]
        cls.ScheduledTaskCv = cls.env["cx.tower.scheduled.task.cv"]

        # apply ssh connection patches
        cls.apply_patches()

    @classmethod
    def apply_patches(cls):
        """
        Apply mock patches for SSH-related methods to simulate various
        scenarios during testing.

        Patches:
        1. SSHConnection.connect:
            - Returns a mock connection with a fake exec_command method,
            which returns a successful or unsuccessful result depending on the
            command content.
        2. SftpService.download_file:
            - Returns b"ok\x00" for files with the .zip extension and
            b"ok" for the rest.
        3. SftpService.upload_file:
            - Returns MagicMock, simulating file upload.
        4. SftpService.delete_file:
            - Returns MagicMock, simulating file deletion.
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
                    stdout_mock.channel.recv_exit_status.return_value = GENERAL_ERROR
                    stdout_mock.readlines.return_value = []
                    stderr_mock.readlines.return_value = ["error"]
                    return stdin_mock, stdout_mock, stderr_mock
                elif "raise" in command:
                    # Simulate an exception
                    raise Exception("error")  # pylint: disable=broad-exception-raised
                else:
                    # Simulate success
                    stdout_mock.channel.recv_exit_status.return_value = 0
                    stdout_mock.readlines.return_value = ["ok"]
                    stderr_mock.readlines.return_value = []
                    return stdin_mock, stdout_mock, stderr_mock

            # Apply side effect to exec_command
            connection_mock.exec_command.side_effect = exec_command_side_effect

            return connection_mock

        connect_patch = patch.object(SSHConnection, "connect", new=ssh_connect)
        connect_patch.start()
        cls.addClassCleanup(connect_patch.stop)

        # Patch file manipulation methods for testing
        def ssh_download_file(self, remote_path):
            if hasattr(self, "env"):
                error = self.env.context.get("raise_download_error")
                if error:
                    raise ValidationError(error)

            _, extension = os.path.splitext(remote_path)
            if extension == ".zip":
                return b"ok\x00"
            return b"ok"

        download_patch = patch.object(
            SftpService, "download_file", new=ssh_download_file
        )
        download_patch.start()
        cls.addClassCleanup(download_patch.stop)

        def ssh_upload_file(self, file, remote_path):
            if hasattr(self, "env"):
                error = self.env.context.get("raise_upload_error")
                if error:
                    raise ValidationError(error)
            return MagicMock()

        upload_patch = patch.object(SftpService, "upload_file", new=ssh_upload_file)
        upload_patch.start()
        cls.addClassCleanup(upload_patch.stop)

        def ssh_delete_file(self, remote_path):
            return MagicMock()

        delete_patch = patch.object(SftpService, "delete_file", new=ssh_delete_file)
        delete_patch.start()
        cls.addClassCleanup(delete_patch.stop)

    @classmethod
    def add_to_group(cls, user, group_refs):
        """Add user to groups

        Args:
            user (res.users): User record
            group_refs (list): Group ref OR List of group references
                eg ['base.group_user', 'some_module.some_group'...]
        """
        if isinstance(group_refs, str):
            group = cls.env.ref(group_refs, raise_if_not_found=False)
            if not group:
                raise ValidationError(_("Group reference %s not found!") % group_refs)
            action = [(4, group.id)]
        elif isinstance(group_refs, list):
            action = []
            for group_ref in group_refs:
                group = cls.env.ref(group_ref, raise_if_not_found=False)
                if not group:
                    raise ValidationError(
                        _("Group reference %s not found!") % group_ref
                    )
                action.append((4, group.id))
        else:
            raise ValidationError(_("groups_ref must be string or list of strings!"))
        user.write({"groups_id": action})

    @classmethod
    def remove_from_group(cls, user, group_refs):
        """Remove user from groups

        Args:
            user (res.users): User record
            group_refs (list): List of group references
                eg ['base.group_user', 'some_module.some_group'...]
        """
        if isinstance(group_refs, str):
            group = cls.env.ref(group_refs, raise_if_not_found=False)
            if not group:
                raise ValidationError(_("Group reference %s not found!") % group_refs)
            action = [(3, group.id)]
        elif isinstance(group_refs, list):
            action = []
            for group_ref in group_refs:
                group = cls.env.ref(group_ref, raise_if_not_found=False)
                if not group:
                    raise ValidationError(
                        _("Group reference %s not found!") % group_ref
                    )
                action.append((3, group.id))
        else:
            raise ValidationError(_("groups_ref must be string or list of strings!"))
        user.write({"groups_id": action})

    @classmethod
    def write_and_invalidate(cls, records, **values):
        """Write values and invalidate cache

        Args:
            records (recordset): recordset to save values
            **values (dict): values to set
        """
        if values:
            records.write(values)
            records.invalidate_recordset(values.keys())
