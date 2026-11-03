# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from .common_jets import TestTowerJetsCommon


class TestJetCloneWizard(TestTowerJetsCommon):
    """Tests for `cx.tower.jet.clone.wizard`"""

    def test_allowed_variable_domain(self):
        """Wizard variable domain follows the allowed variables of the jet template"""
        jet = self.Jet.create(
            {
                "name": "Clone Wizard Jet",
                "jet_template_id": self.jet_template_test.id,
                "server_id": self.server_test_1.id,
            }
        )
        wizard_vals = {"jet_id": jet.id, "state_id": self.state_running.id}
        wizard = self.env["cx.tower.jet.clone.wizard"].create(wizard_vals)
        self.assertEqual(wizard.allowed_variable_domain, [])

        variable = self.Variable.create({"name": "Clone Wizard Allowed Variable"})
        self.jet_template_test.allowed_variable_ids = variable
        wizard = self.env["cx.tower.jet.clone.wizard"].create(wizard_vals)
        self.assertEqual(wizard.allowed_variable_domain, [("id", "in", variable.ids)])
