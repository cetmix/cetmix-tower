# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestTowerCommon(TransactionCase):
    def setUp(self, *args, **kwargs):
        super(TestTowerCommon, self).setUp(*args, **kwargs)
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
        self.os_debian_10 = self.env.ref("cetmix_tower_server.os_debian_10")

        # Server
        self.Server = self.env["cx.tower.server"]
        self.server_test_1 = self.env.ref("cetmix_tower_server.server_test_1")

        # Variable
        self.Variable = self.env["cx.tower.variable"]
        self.VariableValues = self.env["cx.tower.variable.value"]
        self.variable_path = self.env.ref("cetmix_tower_server.variable_path")
        self.variable_dir = self.env.ref("cetmix_tower_server.variable_dir")
        self.variable_os = self.env.ref("cetmix_tower_server.variable_os")
        self.variable_url = self.env.ref("cetmix_tower_server.variable_url")
        self.variable_version = self.env.ref("cetmix_tower_server.variable_version")

        # Command
        self.Command = self.env["cx.tower.command"]
        self.command_create_dir = self.env.ref("cetmix_tower_server.command_create_dir")

        # Command log
        self.CommandLog = self.env["cx.tower.command.log"]

        # Key
        self.Key = self.env["cx.tower.key"]
        self.key_1 = self.env.ref("cetmix_tower_server.key_1")
        self.key_2 = self.env.ref("cetmix_tower_server.key_2")

        # Flight Plans
        self.Plan = self.env["cx.tower.plan"]
        self.plan_line = self.env["cx.tower.plan.line"]
        self.plan_line_action = self.env["cx.tower.plan.line.action"]
        self.plan_1 = self.env.ref("cetmix_tower_server.plan_test_1")

        # Flight plan log
        self.PlanLog = self.env["cx.tower.plan.log"]

        # Patch methods for testing
        def _connect_patch(self, raise_on_error=True):
            """Mock method for connection"""
            return True

        def _execute_command_patch(
            self, client, command, raise_on_error=True, sudo=None, **kwargs
        ):
            """Mock function to test server command execution.
            It will not execute any command but just return a pre-defined result
            Pass "simulated_result" to kwargs for mocked response. Eg:
            "simulated_result": {"status": [0], "response": ["ok"], "error": []}


            Args:
                client (Bool): Anything
                command (Text): Command text
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

            if status != 0:
                if raise_on_error:
                    raise ValidationError(_("SSH execute command error"))
                else:
                    return -1, [], error

            command = self.env["cx.tower.key"].parse_code(
                command, **kwargs.get("key", {})
            )

            if sudo:  # Execute each command separately to avoid extra shell
                status_list = []
                response_list = []
                error_list = []
                while self._prepare_command_for_sudo(command):
                    status_list.append(status)
                    response_list += response
                    error_list += error
                return self._parse_sudo_command_results(
                    status_list, response_list, error_list
                )
            else:
                result = status, response, error
            return result

        self.Server._patch_method("_connect", _connect_patch)
        self.Server._patch_method("_execute_command", _execute_command_patch)

    def tearDown(self):
        # Remove the monkey patches
        self.Server._revert_method("_connect")
        self.Server._revert_method("_execute_command")
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
