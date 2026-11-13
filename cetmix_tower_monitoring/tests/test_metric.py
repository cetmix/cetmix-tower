# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import yaml
from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tools import mute_logger

from .common import TestMonitoringCommon


class TestMetric(TestMonitoringCommon):
    """record_metric and value state."""

    def test_record_metric_create_and_update(self):
        """The first sample creates the value, the next one updates it."""
        metric_value = self.server_test_1.record_metric(
            "test_disk", used=45.2, total=100.0
        )
        self.assertEqual(metric_value.server_id, self.server_test_1)
        self.assertFalse(metric_value.jet_id)
        self.assertEqual(metric_value.value, 45.2)
        self.assertEqual(metric_value.max_value, 100.0)
        self.assertTrue(metric_value.last_update)

        self._make_stale(metric_value, minutes=5)
        previous_update = metric_value.last_update
        updated_value = self.server_test_1.record_metric(
            "test_disk", used=50, total=100
        )
        self.assertEqual(updated_value, metric_value, "Value row must be reused")
        self.assertEqual(metric_value.value, 50)
        self.assertGreater(metric_value.last_update, previous_update)
        self.assertEqual(
            self.MetricValue.search_count(
                [
                    ("metric_id", "=", self.metric_disk.id),
                    ("server_id", "=", self.server_test_1.id),
                ]
            ),
            1,
        )

    def test_record_metric_jet(self):
        """A jet gets its own value row, separate from its server."""
        server_value = self.server_test_1.record_metric("test_load", value=1)
        jet_value = self.jet_sample.record_metric("test_load", value=2)
        self.assertNotEqual(server_value, jet_value)
        self.assertEqual(jet_value.jet_id, self.jet_sample)
        self.assertFalse(jet_value.server_id)
        self.assertEqual(self.jet_sample.metric_value_ids, jet_value)
        self.assertEqual(self.server_test_1.metric_value_ids, server_value)

    @mute_logger("odoo.sql_db")
    def test_value_unique_per_server_and_jet(self):
        """One value per metric and server or jet, never both."""
        self.server_test_1.record_metric("test_load", value=1)
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.MetricValue.create(
                {"metric_id": self.metric_load.id, "server_id": self.server_test_1.id}
            )
        self.jet_sample.record_metric("test_load", value=1)
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.MetricValue.create(
                {"metric_id": self.metric_load.id, "jet_id": self.jet_sample.id}
            )
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.MetricValue.create(
                {
                    "metric_id": self.metric_gauge.id,
                    "server_id": self.server_test_1.id,
                    "jet_id": self.jet_sample.id,
                }
            )
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.MetricValue.create({"metric_id": self.metric_gauge.id})

    def test_record_metric_validation(self):
        """Arguments must match the metric widget."""
        with self.assertRaises(ValidationError):
            self.server_test_1.record_metric("no_such_metric", value=1)
        # Progress bar needs used and total, total > 0
        with self.assertRaises(ValidationError):
            self.server_test_1.record_metric("test_disk", value=1)
        with self.assertRaises(ValidationError):
            self.server_test_1.record_metric("test_disk", used=1)
        with self.assertRaises(ValidationError):
            self.server_test_1.record_metric("test_disk", used=1, total=0)
        with self.assertRaises(ValidationError):
            self.server_test_1.record_metric("test_disk", used="a", total=10)
        # Number needs value
        with self.assertRaises(ValidationError):
            self.server_test_1.record_metric("test_load", used=1, total=2)
        # Values must be finite
        for kwargs in (
            {"metric": "test_disk", "used": "nan", "total": 10},
            {"metric": "test_disk", "used": 1, "total": "nan"},
            {"metric": "test_disk", "used": 1, "total": "inf"},
            {"metric": "test_load", "value": "-inf"},
            {"metric": "test_gauge", "value": 1, "total": "nan"},
        ):
            with self.assertRaises(ValidationError):
                self.server_test_1.record_metric(kwargs.pop("metric"), **kwargs)
        self.assertFalse(self.server_test_1.metric_value_ids)

        # Number ignores total, gauge keeps it
        number_value = self.server_test_1.record_metric("test_load", value=3, total=8)
        self.assertEqual(number_value.max_value, 0)
        gauge_value = self.server_test_1.record_metric("test_gauge", value=3, total=8)
        self.assertEqual(gauge_value.max_value, 8)
        gauge_value = self.server_test_1.record_metric("test_gauge", value=4)
        self.assertEqual(gauge_value.max_value, 0)

    def test_metric_collector_constraint(self):
        """A metric or a value cannot have both a command and a plan."""
        with self.assertRaises(ValidationError):
            self.metric_load.write(
                {
                    "command_id": self.command_report_metric.id,
                    "plan_id": self.plan_collect.id,
                }
            )
        metric_value = self.server_test_1.record_metric("test_load", value=1)
        with self.assertRaises(ValidationError):
            metric_value.write(
                {
                    "command_id": self.command_report_metric.id,
                    "plan_id": self.plan_collect.id,
                }
            )

    def test_state(self):
        """unknown, ok, warning, critical and stale."""
        metric_value = self.MetricValue.create(
            {"metric_id": self.metric_disk.id, "server_id": self.server_test_1.id}
        )
        self.assertEqual(metric_value.state, "unknown")
        self.assertEqual(self.server_test_1.monitoring_state, "unknown")

        with self._patch_run_command():
            self.server_test_1.record_metric("test_disk", used=10, total=100)
            self.assertEqual(metric_value.state, "ok")
            self.assertEqual(self.server_test_1.monitoring_state, "ok")

            self.server_test_1.record_metric("test_disk", used=85, total=100)
            self.assertEqual(metric_value.state, "warning")
            self.assertEqual(self.server_test_1.monitoring_state, "warning")

            self.server_test_1.record_metric("test_disk", used=95, total=100)
            self.assertEqual(metric_value.state, "critical")
            self.assertEqual(
                metric_value.active_threshold_ids,
                self.threshold_disk_warning | self.threshold_disk_critical,
            )

            self.server_test_1.record_metric("test_disk", used=10, total=100)
            self.assertEqual(metric_value.state, "ok")
            self.assertFalse(metric_value.active_threshold_ids)

        self._make_stale(metric_value)
        metric_value.invalidate_recordset(["state"])
        self.MetricValue._cron_check_stale()
        self.assertEqual(metric_value.state, "stale")

    def test_progressbar_compares_percent(self):
        """Progress bar thresholds compare used / total in percent."""
        with self._patch_run_command():
            metric_value = self.server_test_1.record_metric(
                "test_disk", used=7, total=8
            )
        # 87.5 %
        self.assertEqual(metric_value.state, "warning")

    def test_monitoring_state_ranking(self):
        """The server shows the worst state: critical > stale > warning."""
        with self._patch_run_command():
            self.server_test_1.record_metric("test_disk", used=85, total=100)
        load_value = self.server_test_1.record_metric("test_load", value=1)
        self.assertEqual(self.server_test_1.monitoring_state, "warning")

        self._make_stale(load_value)
        self.MetricValue._cron_check_stale()
        self.assertEqual(load_value.state, "stale")
        self.assertEqual(self.server_test_1.monitoring_state, "stale")

        with self._patch_run_command():
            self.server_test_1.record_metric("test_disk", used=95, total=100)
        self.assertEqual(self.server_test_1.monitoring_state, "critical")

    def test_override_thresholds_replace_definition(self):
        """Override thresholds on a value replace the metric thresholds."""
        metric_value = self.server_test_1.record_metric("test_load", value=1)
        self.assertEqual(metric_value.state, "ok")
        self.MetricThreshold.create(
            {
                "metric_id": self.metric_load.id,
                "condition": ">=",
                "value_float": 5,
                "severity": "critical",
            }
        )
        override_threshold = self.MetricThreshold.create(
            {
                "metric_value_id": metric_value.id,
                "condition": ">=",
                "value_float": 1,
                "severity": "warning",
            }
        )
        self.assertEqual(override_threshold.metric_id, self.metric_load)
        self.assertNotIn(override_threshold, self.metric_load.threshold_ids)

        self.server_test_1.record_metric("test_load", value=10)
        self.assertEqual(metric_value.state, "warning")
        self.assertEqual(metric_value.active_threshold_ids, override_threshold)

        # Another server still uses the metric thresholds
        server_2 = self.Server.create(
            {
                "name": "Test Monitoring 2",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "host_key": "test_key",
            }
        )
        other_value = server_2.record_metric("test_load", value=10)
        self.assertEqual(other_value.state, "critical")

    def test_threshold_requirements(self):
        """Severity and the action record are required."""
        with self.assertRaises(ValidationError):
            self.MetricThreshold.create(
                {"metric_id": self.metric_load.id, "condition": ">="}
            )
        with self.assertRaises(ValidationError):
            self.MetricThreshold.create(
                {
                    "metric_id": self.metric_load.id,
                    "severity": "warning",
                    "action": "command",
                }
            )
        with self.assertRaises(ValidationError):
            self.MetricThreshold.create(
                {
                    "metric_id": self.metric_load.id,
                    "severity": "warning",
                    "action": "plan",
                }
            )
        # Stale needs no severity
        stale_threshold = self.MetricThreshold.create(
            {"metric_id": self.metric_load.id, "condition": "stale"}
        )
        self.assertFalse(stale_threshold.severity)

    def test_threshold_reference(self):
        """Threshold references are built from the metric reference."""
        self.assertTrue(
            self.threshold_disk_warning.reference.startswith("test_disk_"),
            self.threshold_disk_warning.reference,
        )

    def test_kanban_metric_data(self):
        """The kanban card shows metrics flagged for kanban only."""
        self.server_test_1.record_metric("test_disk", used=45.25, total=100)
        self.server_test_1.record_metric("test_gauge", value=3, total=8)
        self.server_test_1.record_metric("test_load", value=1.37)
        self.assertEqual(
            self.server_test_1.kanban_metric_data,
            [
                {
                    "name": "Test Disk",
                    "label": "45.25 / 100 GiB",
                    "state": "ok",
                    "percent": 45.25,
                },
                {
                    "name": "Test Gauge",
                    "label": "3",
                    "state": "ok",
                    "percent": False,
                },
            ],
        )

    def test_note_yaml_export_import(self):
        """The metric note is exported and imported with the metric."""
        note = "Root filesystem usage.\nCollected from df."
        self.metric_load.note = note
        yaml_dict = yaml.safe_load(self.metric_load.yaml_code)
        self.assertEqual(yaml_dict["note"], note)

        yaml_dict["reference"] = "test_load_copy"
        vals = self.Metric._post_process_yaml_dict_values(yaml_dict)
        metric_copy = self.Metric.with_context(from_yaml=True).create(vals)
        self.assertEqual(metric_copy.note, note)
