from odoo.exceptions import AccessError
from odoo.orm.model_classes import add_to_registry
from odoo.tools import SQL

from .common import TestTowerBaseCommon


class TestVaultLifecycle(TestTowerBaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from .fake_vault import VaultResource

        add_to_registry(cls.registry, VaultResource)
        cls.registry._setup_models__(cls.env.cr, [VaultResource._name])
        cls.registry.init_models(
            cls.env.cr, [VaultResource._name], {"models_to_check": True}
        )
        cls.addClassCleanup(cls.registry.__delitem__, VaultResource._name)
        cls.Resource = cls.env[VaultResource._name]
        model = cls.env["ir.model"]._get(VaultResource._name)
        cls.env["ir.model.access"].create(
            {
                "name": "Vault test resource",
                "model_id": model.id,
                "group_id": cls.env.ref("base.group_user").id,
                "perm_read": True,
                "perm_write": True,
                "perm_create": True,
                "perm_unlink": True,
            }
        )

    def test_default_secrets_and_required_storage(self):
        record = self.Resource.with_context(default_secret="context default").create({})
        self.assertEqual(record._get_secret_value("secret"), "context default")
        self.assertEqual(
            record._get_secret_value("required_secret"), "required default"
        )
        self.env.cr.execute(
            SQL(
                "SELECT secret, required_secret FROM %s WHERE id = %s",
                SQL.identifier(record._table),
                record.id,
            )
        )
        self.assertEqual(
            self.env.cr.fetchone(), (None, record.SECRET_VALUE_PLACEHOLDER)
        )
        self.assertEqual(record.secret, record.SECRET_VALUE_PLACEHOLDER)
        explicit = self.Resource.with_context(default_secret="ignored").create(
            {"secret": "explicit"}
        )
        self.assertEqual(explicit._get_secret_value("secret"), "explicit")
        field_default = self.Resource.create({})
        self.assertEqual(field_default._get_secret_value("secret"), "field default")

    def test_reused_write_values_and_clear(self):
        records = self.Resource.create([{}, {}])
        vals = {"secret": "replacement"}
        for record in records:
            record.write(vals)
            self.assertEqual(record._get_secret_value("secret"), "replacement")
            self.assertEqual(record.secret, record.SECRET_VALUE_PLACEHOLDER)
        self.assertEqual(vals, {"secret": "replacement"})
        records.write({"secret": ""})
        for record in records:
            self.assertFalse(record._is_secret_value_set("secret"))
        records.write({"secret": ""})
        self.assertFalse(records._get_secret_values(["secret"]))

    def test_restricted_secret_write(self):
        record = self.Resource.create({"restricted_secret": "original"})
        for value in ("replacement", False):
            with self.assertRaises(AccessError):
                record.with_user(self.user_user).write({"restricted_secret": value})
        self.assertEqual(record._get_secret_value("restricted_secret"), "original")
