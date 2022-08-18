from odoo import _
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestTowerCommon(TransactionCase):
    def setUp(self, *args, **kwargs):
        super(TestTowerCommon, self).setUp(*args, **kwargs)

        # Create core elements invoked in the tests

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
