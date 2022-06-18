from odoo.tests.common import TransactionCase


class TestTowerCommon(TransactionCase):
    def setUp(self, *args, **kwargs):
        super(TestTowerCommon, self).setUp(*args, **kwargs)

        # Create core elements invoked in the tests
        # OS
        self.os_debian_10 = self.env["cx.tower.os"].create({"name": "Debian 10"})

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

        # Variables
        self.Variable = self.env["cx.tower.variable"]
        self.VariableValues = self.env["cx.tower.variable.value"]
        self.variable_path = self.Variable.create({"name": "path"})
        self.variable_dir = self.Variable.create({"name": "dir"})
        self.variable_os = self.Variable.create({"name": "os"})
        self.variable_url = self.Variable.create({"name": "url"})
        self.variable_version = self.Variable.create({"name": "version"})

        # Commands
        self.Command = self.env["cx.tower.command"]
        self.command_create_dir = self.Command.create(
            {"name": "Create directory", "code": "cd {{ path }} && mkdir {{ dir }}"}
        )
