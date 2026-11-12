# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import yaml

from odoo.exceptions import AccessError
from odoo.tests.common import new_test_user

from odoo.addons.base.tests.common import BaseCommon


class TestYamlImportAccess(BaseCommon):
    """YAML Import preserves normal permissions and wizard ownership."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        groups = "base.group_user,cetmix_tower_base.group_manager"
        cls.importer = new_test_user(
            cls.env,
            login="yaml_privileged_importer",
            groups=groups + ",cetmix_tower_yaml.group_import",
        )
        cls.other_importer = new_test_user(
            cls.env,
            login="yaml_other_importer",
            groups=groups + ",cetmix_tower_yaml.group_import",
        )
        cls.non_importer = new_test_user(
            cls.env,
            login="yaml_non_importer",
            groups=groups,
        )
        cls.Command = cls.env["cx.tower.command"]
        cls.protected = cls.Command.create(
            {"name": "Protected import target", "access_level": "3", "code": "original"}
        )

    def _wizard(self, values, mode="create"):
        """Build an import wizard owned by the authorized Manager.

        Args:
            values (dict): Command values in YAML format.
            mode (str): Existing-record handling policy.

        Returns:
            cx.tower.yaml.import.wiz: Wizard in the Manager's environment.
        """
        return (
            self.env["cx.tower.yaml.import.wiz"]
            .with_user(self.importer)
            .create(
                {
                    "if_record_exists": mode,
                    "yaml_code": yaml.safe_dump(
                        {
                            "cetmix_tower_yaml_version": 1,
                            "records": [{"cetmix_tower_model": "command", **values}],
                        }
                    ),
                }
            )
        )

    def test_manager_cannot_create_root_command(self):
        wizard = self._wizard(
            {
                "name": "Imported Root command",
                "reference": "yaml_access_root",
                "access_level": "root",
                "code": "imported",
            }
        )
        with self.assertRaises(AccessError):
            wizard.action_import_yaml()
        result = wizard.sudo().action_import_yaml()
        command = self.Command.browse(result["res_id"])
        self.assertEqual(command.access_level, "3")
        self.assertEqual(command.code, "imported")

    def test_manager_cannot_update_root_command(self):
        with self.assertRaises(AccessError):
            self.protected.with_user(self.importer).read(["code"])
        wizard = self._wizard(
            {
                "reference": self.protected.reference,
                "name": self.protected.name,
                "access_level": "root",
                "code": "updated by import",
            },
            mode="update",
        )
        with self.assertRaises(AccessError):
            wizard.action_import_yaml()
        self.assertEqual(self.protected.code, "original")
        result = wizard.sudo().action_import_yaml()
        self.assertEqual(result["res_id"], self.protected.id)
        self.assertEqual(self.protected.code, "updated by import")

    def test_import_requires_permission_and_wizard_ownership(self):
        wizard = self._wizard(
            {"reference": self.protected.reference, "code": "must not be written"},
            mode="update",
        )
        for user in (self.non_importer, self.other_importer):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                wizard.with_user(user).action_import_yaml()
        self.assertEqual(self.protected.code, "original")
