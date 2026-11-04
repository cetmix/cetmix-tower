# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from .common_jets import TestTowerJetsCommon


class TestJetCloneWizard(TestTowerJetsCommon):
    """Tests for `cx.tower.jet.clone.wizard`"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        clone_plan = cls.Plan.create({"name": "Test Clone Plan"})
        cls.jet_template_test.plan_clone_same_server_id = clone_plan
        cls.jet_source = cls.Jet.create(
            {
                "name": "Clone Source",
                "server_id": cls.server_test_1.id,
                "jet_template_id": cls.jet_template_test.id,
                "environment_id": cls.env_prod.id,
            }
        )

    def _clone(self, wizard):
        """Confirm the wizard without running the clone flight plan"""
        with patch.object(type(self.Jet), "run_flight_plan", return_value=None):
            action = wizard.action_confirm()
        return self.Jet.browse(action["res_id"])

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

    def test_environment_default_empty(self):
        """The wizard does not copy the source jet's environment"""
        wizard = self.env["cx.tower.jet.clone.wizard"].create(
            {
                "jet_id": self.jet_source.id,
                "state_id": self.state_running.id,
            }
        )
        self.assertFalse(wizard.environment_id)
        clone = self._clone(wizard)
        self.assertNotEqual(clone, self.jet_source)
        self.assertFalse(clone.environment_id)

    def test_environment_passed(self):
        """The selected environment reaches the cloned jet"""
        wizard = self.env["cx.tower.jet.clone.wizard"].create(
            {
                "jet_id": self.jet_source.id,
                "state_id": self.state_running.id,
                "environment_id": self.env_dev.id,
            }
        )
        clone = self._clone(wizard)
        self.assertEqual(clone.environment_id, self.env_dev)

    def test_env_required_related(self):
        """`env_required` follows the source jet's template"""
        wizard = self.env["cx.tower.jet.clone.wizard"].create(
            {
                "jet_id": self.jet_source.id,
                "state_id": self.state_running.id,
            }
        )
        self.assertFalse(wizard.env_required)
        self.jet_template_test.write(
            {"env_required": True, "environment_default_id": self.env_dev.id}
        )
        wizard.invalidate_recordset(["env_required"])
        self.assertTrue(wizard.env_required)
