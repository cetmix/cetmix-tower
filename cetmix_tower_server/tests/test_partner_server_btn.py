# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests.common import tagged

from .common import TestTowerCommon


@tagged("partner_servers_btn")
class TestPartnerServers(TestTowerCommon):
    def setUp(self):
        super().setUp()
        self.partner_a = self.env["res.partner"].create({"name": "Partner A"})
        self.partner_b = self.env["res.partner"].create({"name": "Partner B"})
        self.partner_b_child = self.env["res.partner"].create(
            {
                "name": "Partner B Child",
                "parent_id": self.partner_b.id,
            }
        )

        self.server_defaults = {
            "name": "Test Server",
            "ssh_username": "root",
            "ssh_port": 22,
            "ssh_password": "Test-P@ssw0rd-123",
            "ip_v4_address": "127.0.0.1",
            "skip_host_key": True,
        }

        self.Server.create({"partner_id": self.partner_b.id, **self.server_defaults})
        self.Server.create({"partner_id": self.partner_b.id, **self.server_defaults})
        self.Server.create(
            {"partner_id": self.partner_b_child.id, **self.server_defaults}
        )

        key = self.Key.create({"name": "SSH Token", "key_type": "s"})
        self.KeyValue.create(
            {
                "key_id": key.id,
                "partner_id": self.partner_b.id,
                "secret_value": "TOPSECRET",
            }
        )

    def test_server_count_compute(self):
        """Server count: direct + one‑level child + zero if none."""
        self.assertEqual(self.partner_b.server_count, 3)
        self.assertEqual(self.partner_b_child.server_count, 1)
        self.assertEqual(self.partner_a.server_count, 0)

    def test_parent_with_only_child_servers(self):
        """Parent witthout servers directs and with child_of."""
        parent = self.env["res.partner"].create({"name": "Parent Only"})
        child = self.env["res.partner"].create(
            {"name": "Child with Server", "parent_id": parent.id}
        )
        self.Server.create({"partner_id": child.id, **self.server_defaults})
        self.assertEqual(parent.server_count, 1)
