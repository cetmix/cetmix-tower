from odoo.tests.common import TransactionCase


class TestTowerCommon(TransactionCase):
    def setUp(self, *args, **kwargs):
        super(TestTowerCommon, self).setUp(*args, **kwargs)

        # Create core elements invoked in the tests
        self.os_debian_10 = self.env["cx.tower.os"].create({"name": "Debian 10"})

        self.Server = self.env["cx.tower.server"]
        self.Variable = self.env["cx.tower.variable"]
        self.VariableValues = self.env["cx.tower.variable.value"]

        # Server 'Test 1'
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
