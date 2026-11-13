# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tools import mute_logger

from .common import TestMonitoringCommon


class TestMetricAutoSync(TestMonitoringCommon):
    """Auto sync cron and deletion of its logs."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ScheduledTask = cls.env["cx.tower.scheduled.task"]
        cls.command_collect_load = cls._create_collector(
            "Test Auto Sync Load", "server.record_metric('test_load', value=2)"
        )

    @classmethod
    def _create_collector(cls, name, code):
        """Create a Python collector command."""
        return cls.Command.create(
            {
                "name": name,
                "action": "python_code",
                "code": f"{code}\nresult = {{'exit_code': 0, 'message': 'ok'}}",
            }
        )

    def _run_cron(self):
        """Run the auto sync cron, commands run in Odoo."""
        with self._patch_defer_handlers([]):
            self.MetricValue._cron_auto_sync()

    def _logs(self, commands=None, plans=None):
        """Return command logs of commands and plan logs of plans."""
        command_logs = self.CommandLog.search(
            [("command_id", "in", commands.ids if commands else [])]
        )
        plan_logs = self.PlanLog.search([("plan_id", "in", plans.ids if plans else [])])
        return command_logs, plan_logs

    def test_auto_sync_minutes_constraint(self):
        """Auto sync is 0 or at least 5 minutes."""
        for minutes in (1, 4, -5):
            with self.assertRaises(ValidationError):
                self.metric_load.auto_sync_minutes = minutes
        self.metric_load.auto_sync_minutes = 0
        self.metric_load.auto_sync_minutes = 5

    def test_auto_sync_off(self):
        """Without auto sync the cron runs nothing."""
        self.metric_load.command_id = self.command_report_metric
        self.server_test_1.record_metric("test_load", value=1)
        with self._patch_run_command() as run_command_mock:
            self.MetricValue._cron_auto_sync()
        run_command_mock.assert_not_called()

    def test_auto_sync_runs_once_per_target(self):
        """A shared collector runs once per server and jet, every N minutes."""
        (self.metric_load | self.metric_gauge).write(
            {"command_id": self.command_report_metric.id, "auto_sync_minutes": 10}
        )
        values = self.MetricValue.create(
            [
                {"metric_id": self.metric_load.id, "server_id": self.server_test_1.id},
                {"metric_id": self.metric_gauge.id, "server_id": self.server_test_1.id},
                {"metric_id": self.metric_load.id, "jet_id": self.jet_sample.id},
            ]
        )
        with self._patch_run_command() as run_command_mock:
            self.MetricValue._cron_auto_sync()
        self.assertEqual(run_command_mock.call_count, 2)
        calls = {
            call.kwargs["jet"]: (call.args, call.kwargs)
            for call in run_command_mock.call_args_list
        }
        self.assertEqual(
            calls[None],
            (
                (self.server_test_1, self.command_report_metric),
                {"jet": None, "log": {"metric_auto_sync": True}},
            ),
        )
        self.assertEqual(
            calls[self.jet_sample][0], (self.server_test_1, self.command_report_metric)
        )
        self.assertTrue(all(values.mapped("last_auto_sync")))

        # Not again before N minutes
        with self._patch_run_command() as run_command_mock:
            self.MetricValue._cron_auto_sync()
        run_command_mock.assert_not_called()

        values.write({"last_auto_sync": fields.Datetime.now() - timedelta(minutes=10)})
        with self._patch_run_command() as run_command_mock:
            self.MetricValue._cron_auto_sync()
        self.assertEqual(run_command_mock.call_count, 2)

    def test_value_collector_override(self):
        """The collector of the value replaces the metric collector."""
        self.metric_load.write(
            {"command_id": self.command_report_metric.id, "auto_sync_minutes": 5}
        )
        self.MetricValue.create(
            {
                "metric_id": self.metric_load.id,
                "server_id": self.server_test_1.id,
                "plan_id": self.plan_collect.id,
            }
        )
        with (
            self._patch_run_command() as run_command_mock,
            self._patch_run_flight_plan() as run_flight_plan_mock,
        ):
            self.MetricValue._cron_auto_sync()
        run_command_mock.assert_not_called()
        self.assertEqual(run_flight_plan_mock.call_count, 1)
        self.assertEqual(
            run_flight_plan_mock.call_args.args,
            (self.server_test_1, self.plan_collect),
        )
        self.assertEqual(
            run_flight_plan_mock.call_args.kwargs,
            {"jet": None, "plan_log": {"metric_auto_sync": True}},
        )

    def test_command_collector_log_deleted(self):
        """The log of a command collector is deleted when the run is done."""
        self.metric_load.write(
            {"command_id": self.command_collect_load.id, "auto_sync_minutes": 5}
        )
        metric_value = self.server_test_1.record_metric("test_load", value=1)

        self._run_cron()
        self.assertEqual(metric_value.value, 2)
        command_logs, _plan_logs = self._logs(commands=self.command_collect_load)
        self.assertFalse(command_logs)

    def test_running_log_kept_until_finished(self):
        """A deferred run keeps its log until it is finished."""
        self.metric_load.write(
            {"command_id": self.command_collect_load.id, "auto_sync_minutes": 5}
        )
        metric_value = self.server_test_1.record_metric("test_load", value=1)

        # Defer every command that has a log, as a queue would
        def defer_logged(command, log_record, *args, **kwargs):
            return bool(log_record)

        with self._patch_defer_handlers([(50, defer_logged)]):
            self.MetricValue._cron_auto_sync()
        command_log, _plan_logs = self._logs(commands=self.command_collect_load)
        self.assertTrue(command_log.metric_auto_sync)
        self.assertTrue(command_log.is_running)

        # Not due yet, but the cron still deletes finished logs
        self.assertTrue(metric_value.last_auto_sync)
        self.MetricValue._cron_auto_sync()
        self.assertTrue(command_log.exists())

        command_log.finish(status=0)
        self.MetricValue._cron_auto_sync()
        self.assertFalse(command_log.exists())

    def test_plan_collector_logs_deleted(self):
        """All logs of a plan collector, nested plans too, are deleted."""
        command_collect_disk = self._create_collector(
            "Test Auto Sync Disk",
            "server.record_metric('test_disk', used=10, total=100)",
        )
        command_collect_gauge = self._create_collector(
            "Test Auto Sync Gauge", "server.record_metric('test_gauge', value=3)"
        )
        child_plan = self.Plan.create(
            {
                "name": "Test Auto Sync Child Plan",
                "line_ids": [(0, 0, {"command_id": command_collect_gauge.id})],
            }
        )
        command_run_child = self.Command.create(
            {
                "name": "Test Auto Sync Run Child Plan",
                "action": "plan",
                "flight_plan_id": child_plan.id,
            }
        )
        parent_plan = self.Plan.create(
            {
                "name": "Test Auto Sync Parent Plan",
                "line_ids": [
                    (0, 0, {"sequence": 10, "command_id": command_collect_disk.id}),
                    (0, 0, {"sequence": 20, "command_id": command_run_child.id}),
                    (
                        0,
                        0,
                        {"sequence": 30, "command_id": self.command_collect_load.id},
                    ),
                ],
            }
        )
        self.metric_load.write({"plan_id": parent_plan.id, "auto_sync_minutes": 5})
        self.MetricValue.create(
            {"metric_id": self.metric_load.id, "server_id": self.server_test_1.id}
        )
        commands = command_collect_disk | command_collect_gauge | command_run_child
        commands |= self.command_collect_load

        self._run_cron()
        # Lines after the first one, and the nested plan, ran
        self.assertEqual(
            self.server_test_1.metric_value_ids.metric_id,
            self.metric_load | self.metric_disk | self.metric_gauge,
        )
        command_logs, plan_logs = self._logs(
            commands=commands, plans=parent_plan | child_plan
        )
        self.assertFalse(command_logs)
        self.assertFalse(plan_logs)

    def test_plan_command_collector_child_logs_deleted(self):
        """A command collector that runs a plan leaves no plan logs."""
        child_plan = self.Plan.create(
            {
                "name": "Test Auto Sync Plan Command",
                "line_ids": [(0, 0, {"command_id": self.command_collect_load.id})],
            }
        )
        command_run_plan = self.Command.create(
            {
                "name": "Test Auto Sync Run Plan",
                "action": "plan",
                "flight_plan_id": child_plan.id,
            }
        )
        self.metric_load.write(
            {"command_id": command_run_plan.id, "auto_sync_minutes": 5}
        )
        metric_value = self.server_test_1.record_metric("test_load", value=1)

        self._run_cron()
        self.assertEqual(metric_value.value, 2)
        command_logs, plan_logs = self._logs(
            commands=command_run_plan | self.command_collect_load, plans=child_plan
        )
        self.assertFalse(command_logs)
        self.assertFalse(plan_logs)

    def test_refused_plan_run_log_kept(self):
        """A plan run refused because another one is running keeps its log."""
        self.metric_load.write(
            {"plan_id": self.plan_collect.id, "auto_sync_minutes": 5}
        )
        self.MetricValue.create(
            {"metric_id": self.metric_load.id, "server_id": self.server_test_1.id}
        )
        running_log = self.PlanLog.create(
            {
                "server_id": self.server_test_1.id,
                "plan_id": self.plan_collect.id,
                "start_date": fields.Datetime.now(),
            }
        )
        self.assertTrue(running_log.is_running)

        self._run_cron()
        _command_logs, plan_logs = self._logs(plans=self.plan_collect)
        refused_log = plan_logs - running_log
        self.assertEqual(len(refused_log), 1)
        self.assertFalse(refused_log.metric_auto_sync)

    def test_threshold_action_log_kept(self):
        """A threshold action started during the sync keeps its log."""
        command_collect_disk = self._create_collector(
            "Test Auto Sync Critical Disk",
            "server.record_metric('test_disk', used=95, total=100)",
        )
        self.metric_disk.write(
            {"command_id": command_collect_disk.id, "auto_sync_minutes": 5}
        )
        self.MetricValue.create(
            {"metric_id": self.metric_disk.id, "server_id": self.server_test_1.id}
        )

        self._run_cron()
        collector_logs, _plan_logs = self._logs(commands=command_collect_disk)
        report_logs, _plan_logs = self._logs(commands=self.command_report_metric)
        self.assertFalse(collector_logs)
        self.assertEqual(len(report_logs), 1)
        self.assertFalse(report_logs.metric_auto_sync)

    def test_refresh_and_scheduled_task_keep_logs(self):
        """Refresh and Scheduled Task runs keep their logs."""
        self.metric_load.write(
            {"command_id": self.command_collect_load.id, "auto_sync_minutes": 5}
        )
        self.server_test_1.record_metric("test_load", value=1)
        scheduled_task = self.ScheduledTask.create(
            {
                "name": "Test Auto Sync Scheduled Task",
                "action": "command",
                "command_id": self.command_collect_load.id,
                "server_ids": [(4, self.server_test_1.id)],
            }
        )

        with self._patch_defer_handlers([]):
            self.server_test_1.action_refresh_metrics()
            scheduled_task.action_run()
        self.MetricValue._delete_metric_auto_sync_logs()

        command_logs, _plan_logs = self._logs(commands=self.command_collect_load)
        self.assertEqual(len(command_logs), 2)
        self.assertFalse(any(command_logs.mapped("metric_auto_sync")))

    @mute_logger("odoo.addons.cetmix_tower_monitoring.models.cx_tower_metric_value")
    def test_failing_collector_does_not_stop_others(self):
        """A collector that raises does not stop the other collectors."""
        command_broken = self._create_collector("Test Auto Sync Broken", "pass")
        self.metric_gauge.write(
            {"command_id": command_broken.id, "auto_sync_minutes": 5}
        )
        self.metric_load.write(
            {"command_id": self.command_collect_load.id, "auto_sync_minutes": 5}
        )
        # The broken collector runs first
        values = self.MetricValue.create(
            [
                {"metric_id": self.metric_gauge.id, "server_id": self.server_test_1.id},
                {"metric_id": self.metric_load.id, "server_id": self.server_test_1.id},
            ]
        )
        server_model = self.registry["cx.tower.server"]
        run_command = server_model.run_command

        def run_command_or_raise(server, command, *args, **kwargs):
            if command == command_broken:
                raise UserError(self.env._("Rendering failed"))
            return run_command(server, command, *args, **kwargs)

        with (
            patch.object(
                server_model,
                "run_command",
                autospec=True,
                side_effect=run_command_or_raise,
            ),
            self._patch_defer_handlers([]),
        ):
            self.MetricValue._cron_auto_sync()

        load_value = values.filtered(lambda v: v.metric_id == self.metric_load)
        self.assertEqual(load_value.value, 2)
        self.assertTrue(all(values.mapped("last_auto_sync")))
