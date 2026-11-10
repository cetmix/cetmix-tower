# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import yaml

from odoo.exceptions import AccessError, ValidationError
from odoo.tools import mute_logger

from .common import TestMonitoringCommon


class TestJetTemplateMetric(TestMonitoringCommon):
    """Metrics defined on a Jet Template are synced to its jets."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.JetTemplateMetric = cls.env["cx.tower.jet.template.metric"]
        cls.jet_template = cls.jet_template_sample

    def _create_jet(self, name, environment=None):
        """Create a jet of the sample template on the sample server."""
        return self.Jet.create(
            {
                "name": name,
                "jet_template_id": self.jet_template.id,
                "server_id": self.server_test_1.id,
                "environment_id": environment.id if environment else False,
            }
        )

    def _add_template_metric(self, metric, environments=None):
        """Add a metric to the sample Jet Template."""
        return self.JetTemplateMetric.create(
            {
                "jet_template_id": self.jet_template.id,
                "metric_id": metric.id,
                "environment_ids": [(6, 0, environments.ids if environments else [])],
            }
        )

    def _values_by_metric(self, jet):
        """Return {metric: value} for the values of a jet."""
        return {value.metric_id: value for value in jet.metric_value_ids}

    def test_new_jet_gets_template_values(self):
        """New jets get non-manual values for the applicable metrics only."""
        self._add_template_metric(self.metric_load)
        self._add_template_metric(self.metric_gauge, self.env_prod)

        jet_stage = self._create_jet("Test Metric Jet Stage", self.env_stage)
        self.assertEqual(jet_stage.metric_value_ids.metric_id, self.metric_load)
        self.assertFalse(jet_stage.metric_value_ids.manual)

        jet_prod = self._create_jet("Test Metric Jet Prod", self.env_prod)
        self.assertEqual(
            jet_prod.metric_value_ids.metric_id, self.metric_load | self.metric_gauge
        )
        self.assertFalse(any(jet_prod.metric_value_ids.mapped("manual")))

        jet_no_environment = self._create_jet("Test Metric Jet No Env")
        self.assertEqual(
            jet_no_environment.metric_value_ids.metric_id, self.metric_load
        )

    def test_template_changes_reach_existing_jets(self):
        """Adding and removing template metrics updates existing jets."""
        manual_value = self.jet_sample.record_metric("test_load", value=1)
        self.assertTrue(manual_value.manual)

        template_metric_gauge = self._add_template_metric(self.metric_gauge)
        template_metric_load = self._add_template_metric(self.metric_load)
        values = self._values_by_metric(self.jet_sample)
        self.assertFalse(values[self.metric_gauge].manual)
        # The manual value wins: no duplicate, stays manual
        self.assertEqual(values[self.metric_load], manual_value)
        self.assertTrue(manual_value.manual)
        self.assertEqual(len(self.jet_sample.metric_value_ids), 2)

        gauge_value = values[self.metric_gauge]
        (template_metric_gauge | template_metric_load).unlink()
        self.assertEqual(self.jet_sample.metric_value_ids, manual_value)
        self.assertFalse(gauge_value.exists())

    def test_environment_changes(self):
        """Environments on template metrics and on jets add/remove values."""
        template_metric = self._add_template_metric(self.metric_gauge, self.env_prod)
        jet = self._create_jet("Test Metric Jet Env", self.env_stage)
        self.assertFalse(jet.metric_value_ids)

        # Template metric now applies to staging
        template_metric.environment_ids = [(4, self.env_stage.id)]
        self.assertEqual(jet.metric_value_ids.metric_id, self.metric_gauge)

        # Jet moves to development: not applicable any more
        jet.environment_id = self.env_dev
        self.assertFalse(jet.metric_value_ids)

        # No environments: all jets
        template_metric.environment_ids = [(5, 0, 0)]
        self.assertEqual(jet.metric_value_ids.metric_id, self.metric_gauge)

    def test_record_metric_value_stays_manual(self):
        """record_metric() creates a manual value that template sync keeps."""
        template_metric = self._add_template_metric(self.metric_gauge)
        manual_value = self.jet_sample.record_metric("test_load", value=1)
        self.assertTrue(manual_value.manual)

        # Template value is updated by record_metric() and stays non-manual
        gauge_value = self.jet_sample.record_metric("test_gauge", value=2)
        self.assertFalse(gauge_value.manual)

        template_metric.environment_ids = [(6, 0, self.env_prod.ids)]
        self.assertEqual(self.jet_sample.metric_value_ids, manual_value)

    def test_manager_edits_template_of_inaccessible_jet(self):
        """Template lines can be changed without access to every jet."""
        self.jet_template.write({"manager_ids": [(4, self.manager.id)]})
        self.assertNotIn(self.manager, self.jet_sample.manager_ids)

        self.jet_template.with_user(self.manager).write(
            {"metric_ids": [(0, 0, {"metric_id": self.metric_load.id})]}
        )
        self.assertEqual(self.jet_sample.metric_value_ids.metric_id, self.metric_load)

        self.jet_template.metric_ids.with_user(self.manager).unlink()
        self.assertFalse(self.jet_sample.metric_value_ids)

    def test_copied_jet_gets_template_values(self):
        """A copied jet gets its template values once."""
        self._add_template_metric(self.metric_load)
        self.jet_sample.record_metric("test_gauge", value=1)

        jet_copy = self.jet_sample.copy({"name": "Test Metric Jet Copy"})
        self.assertEqual(jet_copy.metric_value_ids.metric_id, self.metric_load)
        self.assertFalse(jet_copy.metric_value_ids.manual)

    def test_environment_in_use_cannot_be_deleted(self):
        """An environment used in a template metric cannot be deleted."""
        environment = self.Environment.create({"name": "Test Metric Env"})
        self._add_template_metric(self.metric_load, environment)
        with self.assertRaises(ValidationError):
            environment.unlink()

    def test_yaml_export_import(self):
        """Template metric lines are exported and imported with the template."""
        jet_template = self.JetTemplate.create(
            {
                "name": "Test Metric YAML Template",
                "reference": "test_metric_yaml_template",
                "metric_ids": [
                    (
                        0,
                        0,
                        {
                            "metric_id": self.metric_load.id,
                            "environment_ids": [(6, 0, self.env_prod.ids)],
                        },
                    ),
                    (0, 0, {"metric_id": self.metric_gauge.id}),
                ],
            }
        )

        yaml_dict = yaml.safe_load(jet_template.yaml_code)
        exported = {
            line["metric_id"]: line.get("environment_ids")
            for line in yaml_dict["metric_ids"]
        }
        self.assertEqual(exported["test_load"], ["test_prod"])
        self.assertFalse(exported["test_gauge"])

        jet_template.unlink()
        vals = self.JetTemplate._post_process_yaml_dict_values(yaml_dict)
        restored = self.JetTemplate.with_context(from_yaml=True).create(vals)
        self.assertEqual(
            restored.metric_ids.metric_id, self.metric_load | self.metric_gauge
        )
        load_line = restored.metric_ids.filtered(
            lambda line: line.metric_id == self.metric_load
        )
        self.assertEqual(load_line.environment_ids, self.env_prod)

    @mute_logger("odoo.addons.base.models.ir_rule", "odoo.addons.base.models.ir_model")
    def test_access(self):
        """Template metric lines follow the access of the Jet Template."""
        template_metric = self._add_template_metric(self.metric_load)
        self.jet_template.write({"access_level": "3"})
        self.assertFalse(
            self.JetTemplateMetric.with_user(self.manager).search(
                [("id", "=", template_metric.id)]
            )
        )
        self.jet_template.write({"user_ids": [(4, self.manager.id)]})
        self.assertEqual(
            self.JetTemplateMetric.with_user(self.manager).search(
                [("id", "=", template_metric.id)]
            ),
            template_metric,
        )
        with self.assertRaises(AccessError):
            self.JetTemplateMetric.with_user(self.user).search([])
