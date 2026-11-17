# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import timedelta
from unittest.mock import patch

from odoo import fields

from odoo.addons.cetmix_tower_server.tests.common import TestTowerCommon


class TestMonitoringCommon(TestTowerCommon):
    """Common fixtures for Cetmix Tower Monitoring tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.Metric = cls.env["cx.tower.metric"]
        cls.MetricThreshold = cls.env["cx.tower.metric.threshold"]
        cls.MetricValue = cls.env["cx.tower.metric.value"]

        # Python command that reports the threshold eval context
        cls.command_report_metric = cls.Command.create(
            {
                "name": "Test Report Metric",
                "reference": "test_report_metric",
                "action": "python_code",
                "code": (
                    "result = {'exit_code': 0, 'message': '%s|%s|%s' % ("
                    "metric and metric.reference, "
                    "metric_value and metric_value.id, "
                    "jet and jet.reference)}"
                ),
            }
        )
        cls.plan_collect = cls.Plan.create({"name": "Test Collect Plan"})

        cls.metric_disk = cls.Metric.create(
            {
                "name": "Test Disk",
                "reference": "test_disk",
                "widget": "progressbar",
                "unit": "GiB",
                "stale_after_minutes": 30,
            }
        )
        cls.threshold_disk_warning = cls.MetricThreshold.create(
            {
                "metric_id": cls.metric_disk.id,
                "sequence": 10,
                "condition": ">=",
                "value_float": 80,
                "severity": "warning",
                "action": "none",
            }
        )
        cls.threshold_disk_critical = cls.MetricThreshold.create(
            {
                "metric_id": cls.metric_disk.id,
                "sequence": 20,
                "condition": ">=",
                "value_float": 90,
                "severity": "critical",
                "action": "command",
                "command_id": cls.command_report_metric.id,
            }
        )
        cls.metric_load = cls.Metric.create(
            {
                "name": "Test Load",
                "reference": "test_load",
                "widget": "number",
                "show_on_kanban": False,
            }
        )
        cls.metric_gauge = cls.Metric.create(
            {
                "name": "Test Gauge",
                "reference": "test_gauge",
                "widget": "gauge",
            }
        )

    def _make_stale(self, metric_value, minutes=60):
        """Move the last update of a value to the past.

        Args:
            metric_value (cx.tower.metric.value()): Value.
            minutes (int): How many minutes ago.
        """
        metric_value.sudo().write(
            {"last_update": fields.Datetime.now() - timedelta(minutes=minutes)}
        )

    def _patch_run_command(self):
        """Mock ``cx.tower.server.run_command``.

        Returns:
            unittest.mock._patch: Patch with autospec, the first call
                argument is the server record.
        """
        return patch.object(
            self.registry["cx.tower.server"], "run_command", autospec=True
        )

    def _patch_run_flight_plan(self):
        """Mock ``cx.tower.server.run_flight_plan``.

        Returns:
            unittest.mock._patch: Patch with autospec, the first call
                argument is the server record.
        """
        return patch.object(
            self.registry["cx.tower.server"], "run_flight_plan", autospec=True
        )
