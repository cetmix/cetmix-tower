# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase


class TestTowerCommon(TransactionCase):
    def setUp(self, *args, **kwargs):
        super().setUp(*args, **kwargs)
        # ***
        # Create core elements invoked in the tests
        # ***

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
        self.VariableValues = self.env["cx.tower.variable.value"]

        self.variable_path = self.Variable.create({"name": "test_path_"})
        self.variable_dir = self.Variable.create({"name": "test_dir"})
        self.variable_os = self.Variable.create({"name": "test_os"})
        self.variable_url = self.Variable.create({"name": "test_url"})
        self.variable_version = self.Variable.create({"name": "test_version"})

        # Key
        self.Key = self.env["cx.tower.key"]

        self.key_1 = self.Key.create({"name": "Test Key 1"})
        self.secret_2 = self.Key.create({"name": "Test Key 2", "key_type": "s"})

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
                "tag_ids": [
                    (6, 0, [self.env.ref("cetmix_tower_server.tag_staging").id])
                ],
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

        # Patch methods for testing
        def _connect_patch(self, raise_on_error=True):
            """Mock method for connection"""
            return True

        def _execute_command_using_ssh_patch(
            self,
            client,
            command_code,
            command_path=None,
            raise_on_error=True,
            sudo=None,
            **kwargs,
        ):
            """Mock function to test server command execution.
            It will not execute any command but just return a pre-defined result
            Pass "simulated_result" to kwargs for mocked response. Eg:
            "simulated_result": {"status": [0], "response": ["ok"], "error": []}


            Args:
                client (Bool): Anything
                command_code (Text): Command text
                command_path (Char, optional): Directory where command is executed
                raise_on_error (bool, optional): raise if error Defaults to True.
                sudo (selection, optional): Use sudo for commands. Defaults to None.

            Returns:
            status, [response], [error]
            """

            simulated_result = kwargs.get("simulated_result")
            if simulated_result:
                status = simulated_result["status"]
                response = simulated_result["response"]
                error = simulated_result["error"]
            else:
                status = 0
                response = ["ok"]
                error = []

            # Parse inline secrets
            code_and_secrets = self.env[
                "cx.tower.key"
            ]._parse_code_and_return_key_values(command_code, **kwargs.get("key", {}))
            command_code = code_and_secrets["code"]
            secrets = code_and_secrets["key_values"]

            command = self.env["cx.tower.key"]._parse_code(
                command_code, **kwargs.get("key", {})
            )

            if status != 0:
                if raise_on_error:
                    raise ValidationError(_("SSH execute command error"))
                return self._parse_ssh_command_results(-1, [], error, secrets, **kwargs)

            command = self._prepare_ssh_command(command, command_path, sudo)

            # Compose response multiple commands: sudo with password
            if isinstance(command, list):
                status_list = []
                response_list = []
                error_list = []
                for cmd in command:  # pylint: disable=unused-variable # noqa
                    status_list.append(status)
                    response_list += response
                    error_list += error

            return self._parse_ssh_command_results(
                status, response, error, secrets, **kwargs
            )

        self.Server._patch_method("_connect", _connect_patch)
        self.Server._patch_method(
            "_execute_command_using_ssh", _execute_command_using_ssh_patch
        )

    def tearDown(self):
        # Remove the monkey patches
        self.Server._revert_method("_connect")
        self.Server._revert_method("_execute_command_using_ssh")
        super(TestTowerCommon, self).tearDown()

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
