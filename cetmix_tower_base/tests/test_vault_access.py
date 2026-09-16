# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError

from .common import TestTowerBaseCommon


class TestVaultAccess(TestTowerBaseCommon):
    """ACL-only protection of cx.tower.vault after dropping rpc_helper."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_system = cls.Users.create(
            {
                "name": "Tower System Admin",
                "login": "tower_system_admin",
                "email": "tower_system_admin@example.com",
                "groups_id": [(6, 0, [cls.env.ref("base.group_system").id])],
            }
        )
        cls.Vault = cls.env["cx.tower.vault"]

    def _vault_vals(self, field_name):
        return {
            "res_model": "res.users",
            "res_id": self.user_internal.id,
            "field_name": field_name,
            "data": "secret",
        }

    def test_no_acl_grants_access(self):
        """Every active ACL row for the vault denies all four permissions."""
        accesses = self.env["ir.model.access"].search(
            [
                ("model_id.model", "=", "cx.tower.vault"),
                ("active", "=", True),
            ]
        )
        self.assertTrue(accesses)
        for access in accesses:
            self.assertFalse(access.perm_read)
            self.assertFalse(access.perm_write)
            self.assertFalse(access.perm_create)
            self.assertFalse(access.perm_unlink)

    def test_tower_groups_and_admins_are_denied(self):
        """Tower groups and Settings admins cannot CRUD the vault without sudo."""
        record = self.Vault.sudo().create(self._vault_vals("denied_secret"))
        users = (
            self.user_user,
            self.user_manager,
            self.user_root,
            self.user_system,
        )
        for user in users:
            vault = self.Vault.with_user(user)
            with self.assertRaises(AccessError):
                vault.search([])
            with self.assertRaises(AccessError):
                record.with_user(user).read(["data"])
            with self.assertRaises(AccessError):
                vault.search_read([], ["data"])
            with self.assertRaises(AccessError):
                vault.create(self._vault_vals(f"create_{user.login}"))
            with self.assertRaises(AccessError):
                record.with_user(user).write({"data": "changed"})
            with self.assertRaises(AccessError):
                record.with_user(user).unlink()

    def test_sudo_still_works(self):
        """The vault mixin depends on sudo() succeeding for CRUD."""
        record = self.Vault.sudo().create(self._vault_vals("sudo_secret"))
        self.assertTrue(self.Vault.sudo().search([("id", "=", record.id)]))
        self.assertEqual(record.sudo().read(["data"])[0]["data"], "secret")
        self.assertEqual(
            self.Vault.sudo().search_read([("id", "=", record.id)], ["data"])[0][
                "data"
            ],
            "secret",
        )
        extra = self.Vault.sudo().create(self._vault_vals("sudo_secret_extra"))
        extra.sudo().write({"data": "changed"})
        self.assertEqual(extra.sudo().data, "changed")
        extra.sudo().unlink()
        self.assertFalse(extra.exists())
        record.sudo().unlink()
