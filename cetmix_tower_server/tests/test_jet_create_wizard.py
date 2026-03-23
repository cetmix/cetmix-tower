# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from .common_jets import TestTowerJetsCommon


class TestJetCreateWizard(TestTowerJetsCommon):
    """Tests for `cx.tower.jet.create.wizard`"""

    def test_action_confirm_creates_jet(self):
        """
        Ensure that the wizard creates a new jet using the selected template.
        """
        wizard_model = self.env["cx.tower.jet.create.wizard"]

        wizard = wizard_model.create(
            {
                "name_type": "m",
                "name": "Wizard Jet",
                "jet_template_id": self.jet_template_test.id,
                "server_id": self.server_test_1.id,
            }
        )

        action = wizard.action_confirm()

        jet = self.Jet.browse(action["res_id"])
        self.assertTrue(jet.exists(), "Wizard action should return the created jet")
        self.assertEqual(jet.name, "Wizard Jet")
        self.assertEqual(jet.server_id, self.server_test_1)
        self.assertEqual(jet.jet_template_id, self.jet_template_test)

    def test_action_confirm_sets_custom_variables(self):
        """
        Ensure custom variable values from the wizard are stored on the created jet.
        """
        wizard_model = self.env["cx.tower.jet.create.wizard"]
        custom_variable = self.Variable.create(
            {
                "name": "Wizard Custom Variable",
            }
        )
        custom_value = "custom value"

        wizard = wizard_model.create(
            {
                "name_type": "m",
                "name": "Wizard Jet With Variables",
                "jet_template_id": self.jet_template_test.id,
                "server_id": self.server_test_1.id,
                "use_custom_variables": "y",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "variable_id": custom_variable.id,
                            "value_char": custom_value,
                        },
                    )
                ],
            }
        )

        action = wizard.action_confirm()
        jet = self.Jet.browse(action["res_id"])
        custom_lines = jet.variable_value_ids.filtered(
            lambda line: line.variable_id == custom_variable
        )

        self.assertEqual(len(custom_lines), 1, "Custom variable should be stored once")
        self.assertEqual(
            custom_lines.variable_id,
            custom_variable,
            "Custom variable record should be linked to the expected variable",
        )
        self.assertEqual(
            custom_lines.value_char,
            custom_value,
            "Created jet should keep custom variable values from the wizard",
        )
