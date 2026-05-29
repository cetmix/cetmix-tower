# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests.common import tagged

from .common import TestTowerCommon


@tagged("partner_servers_btn")
class TestPartnerServers(TestTowerCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_a = cls.env["res.partner"].create({"name": "Partner A"})
        cls.partner_b = cls.env["res.partner"].create({"name": "Partner B"})
        cls.partner_b_child = cls.env["res.partner"].create(
            {
                "name": "Partner B Child",
                "parent_id": cls.partner_b.id,
            }
        )

        cls.server_defaults = {
            "name": "Test Server",
            "ssh_username": "root",
            "ssh_port": 22,
            "ssh_password": "Test-P@ssw0rd-123",
            "ip_v4_address": "127.0.0.1",
            "skip_host_key": True,
        }

        cls.Server.create({"partner_id": cls.partner_b.id, **cls.server_defaults})
        cls.Server.create({"partner_id": cls.partner_b.id, **cls.server_defaults})
        cls.Server.create({"partner_id": cls.partner_b_child.id, **cls.server_defaults})

        key = cls.Key.create({"name": "SSH Token", "key_type": "s"})
        cls.KeyValue.create(
            {
                "key_id": key.id,
                "partner_id": cls.partner_b.id,
                "secret_value": "TOPSECRET",
            }
        )

    def test_server_count_compute(self):
        """Server count: direct + one‑level child + zero if none."""
        self.assertEqual(self.partner_b.server_count, 3)
        self.assertEqual(self.partner_b_child.server_count, 1)
        self.assertEqual(self.partner_a.server_count, 0)

    def test_parent_with_only_child_servers(self):
        """Parent without servers directs and with child_of."""
        parent = self.env["res.partner"].create({"name": "Parent Only"})
        child = self.env["res.partner"].create(
            {"name": "Child with Server", "parent_id": parent.id}
        )
        self.Server.create({"partner_id": child.id, **self.server_defaults})
        self.assertEqual(parent.server_count, 1)
