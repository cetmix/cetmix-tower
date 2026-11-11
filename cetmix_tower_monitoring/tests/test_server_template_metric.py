# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import yaml

from .common import TestMonitoringCommon


class TestServerTemplateMetric(TestMonitoringCommon):
    """Metrics defined on Server Templates."""

    def _create_server(self, name):
        """Create a server from the sample template.

        Args:
            name (str): Server name.

        Returns:
            cx.tower.server(): New server
        """
        return self.ServerTemplate.create_server_from_template(
            self.server_template_sample.reference, name, ipv4="0.0.0.0"
        )

    def test_new_server_gets_template_metrics(self):
        """A server created from the template gets one value per metric."""
        self.server_template_sample.metric_ids = self.metric_load | self.metric_gauge
        server = self._create_server("Test Metric Template Server")
        self.assertEqual(
            server.metric_value_ids.metric_id, self.metric_load | self.metric_gauge
        )
        self.assertEqual(len(server.metric_value_ids), 2)
        self.assertEqual(set(server.metric_value_ids.mapped("state")), {"unknown"})

    def test_template_without_metrics(self):
        """A template without metrics gives a server without values."""
        server = self._create_server("Test No Metric Template Server")
        self.assertFalse(server.metric_value_ids)

    def test_template_changes_do_not_reach_servers(self):
        """Metrics are copied once, on server creation."""
        self.server_template_sample.metric_ids = self.metric_load
        server = self._create_server("Test Metric Copy Once Server")

        self.server_template_sample.metric_ids = self.metric_gauge
        self.assertEqual(server.metric_value_ids.metric_id, self.metric_load)

        self.server_template_sample.metric_ids = False
        self.assertEqual(server.metric_value_ids.metric_id, self.metric_load)

    def test_yaml_export_import(self):
        """Template metrics are exported and imported as references."""
        server_template = self.ServerTemplate.create(
            {
                "name": "Test Metric YAML Server Template",
                "reference": "test_metric_yaml_server_template",
                "metric_ids": [(6, 0, (self.metric_load | self.metric_gauge).ids)],
            }
        )

        yaml_dict = yaml.safe_load(server_template.yaml_code)
        self.assertEqual(sorted(yaml_dict["metric_ids"]), ["test_gauge", "test_load"])

        server_template.unlink()
        vals = self.ServerTemplate._post_process_yaml_dict_values(yaml_dict)
        restored = self.ServerTemplate.with_context(from_yaml=True).create(vals)
        self.assertEqual(restored.metric_ids, self.metric_load | self.metric_gauge)
