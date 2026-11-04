# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""YAML export/import of environments on variable values and Jet Templates."""

import yaml

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestEnvironmentYAML(TransactionCase):
    """Environments are exported and imported as references"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.Environment = cls.env["cx.tower.environment"]
        cls.JetTemplate = cls.env["cx.tower.jet.template"]
        cls.Variable = cls.env["cx.tower.variable"]
        cls.VariableValue = cls.env["cx.tower.variable.value"]

        cls.env_prod = cls.Environment.create(
            {"name": "Test Production", "reference": "test_prod"}
        )
        cls.env_stage = cls.Environment.create(
            {"name": "Test Staging", "reference": "test_stage"}
        )
        cls.env_dev = cls.Environment.create(
            {"name": "Test Development", "reference": "test_dev"}
        )
        cls.variable = cls.Variable.create(
            {"name": "YAML Env Workers", "reference": "test_yaml_env_workers"}
        )
        cls.jet_template = cls.JetTemplate.create(
            {
                "name": "YAML Env Template",
                "reference": "test_yaml_env_template",
                "env_required": True,
                "environment_default_id": cls.env_dev.id,
                "variable_value_ids": [
                    (
                        0,
                        0,
                        {
                            "variable_id": cls.variable.id,
                            "value_char": "8",
                            "environment_ids": [
                                (6, 0, (cls.env_prod | cls.env_stage).ids)
                            ],
                        },
                    ),
                    (0, 0, {"variable_id": cls.variable.id, "value_char": "2"}),
                ],
            }
        )

    def _value_by_char(self, values, value_char):
        """Return the YAML value dict with the given value"""
        return next(v for v in values if v["value_char"] == value_char)

    def test_export(self):
        """Environments are exported as reference strings"""
        data = yaml.safe_load(self.jet_template.yaml_code)
        self.assertIs(data["env_required"], True)
        self.assertEqual(data["environment_default_id"], "test_dev")

        values = data["variable_value_ids"]
        tagged_value = self._value_by_char(values, "8")
        self.assertEqual(
            sorted(tagged_value["environment_ids"]), ["test_prod", "test_stage"]
        )
        untagged_value = self._value_by_char(values, "2")
        self.assertFalse(untagged_value.get("environment_ids"))

    def test_import(self):
        """References are resolved on import"""
        yaml_dict = yaml.safe_load(self.jet_template.yaml_code)
        self.jet_template.unlink()

        vals = self.JetTemplate._post_process_yaml_dict_values(yaml_dict)
        restored = self.JetTemplate.with_context(from_yaml=True).create(vals)

        self.assertTrue(restored.env_required)
        self.assertEqual(restored.environment_default_id, self.env_dev)
        values = restored.variable_value_ids
        self.assertEqual(len(values), 2)
        tagged_value = values.filtered(lambda v: v.value_char == "8")
        self.assertEqual(tagged_value.environment_ids, self.env_prod | self.env_stage)
        untagged_value = values.filtered(lambda v: v.value_char == "2")
        self.assertFalse(untagged_value.environment_ids)

    def test_import_unknown_reference_dropped(self):
        """An unknown environment reference is dropped on import:
        the value applies to all environments
        """
        vals = self.VariableValue._post_process_yaml_dict_values(
            {
                "variable_id": self.variable.reference,
                "value_char": "4",
                "environment_ids": ["test_prod", "test_no_such_env"],
            }
        )
        value = self.VariableValue.with_context(from_yaml=True).create(vals)
        self.assertEqual(value.environment_ids, self.env_prod)

        vals = self.VariableValue._post_process_yaml_dict_values(
            {
                "variable_id": self.variable.reference,
                "value_char": "5",
                "environment_ids": ["test_no_such_env"],
            }
        )
        value = self.VariableValue.with_context(from_yaml=True).create(vals)
        self.assertFalse(value.environment_ids)
