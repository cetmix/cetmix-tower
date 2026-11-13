# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from .common import TestMonitoringCommon

CUSTOM_VALUE_KEYS = {
    "__metric__",
    "__metric_value__",
    "__metric_max__",
    "__metric_unit__",
    "__metric_state__",
    "__metric_previous_state__",
    "__metric_severity__",
    "__server__",
    "__jet__",
}


class TestMetricThreshold(TestMonitoringCommon):
    """Threshold transitions, actions and their eval context."""

    def _report_responses(self, command):
        """Return responses of the command logs of a command."""
        return self.CommandLog.search(
            [("command_id", "=", command.id)], order="id"
        ).mapped("command_response")

    def test_action_runs_once_on_transition(self):
        """The command runs when the threshold becomes matched, not again."""
        with self._patch_run_command() as run_command_mock:
            # First sample already over the limit runs the action
            metric_value = self.server_test_1.record_metric(
                "test_disk", used=95, total=100
            )
            self.assertEqual(run_command_mock.call_count, 1)

            # Still over the limit: no new run
            self.server_test_1.record_metric("test_disk", used=96, total=100)
            self.assertEqual(run_command_mock.call_count, 1)

            # Back to normal and over the limit again: runs again
            self.server_test_1.record_metric("test_disk", used=10, total=100)
            self.server_test_1.record_metric("test_disk", used=99, total=100)
            self.assertEqual(run_command_mock.call_count, 2)

        server, command = run_command_mock.call_args.args
        kwargs = run_command_mock.call_args.kwargs
        self.assertEqual(server, self.server_test_1)
        self.assertEqual(command, self.command_report_metric)
        self.assertIsNone(kwargs["jet"])
        self.assertEqual(kwargs["log"], {})
        self.assertEqual(kwargs["metric"], self.metric_disk)
        self.assertEqual(kwargs["metric_value"], metric_value)
        custom_values = kwargs["variable_values"]
        self.assertEqual(set(custom_values), CUSTOM_VALUE_KEYS)
        self.assertEqual(custom_values["__metric__"], "test_disk")
        self.assertEqual(custom_values["__metric_value__"], "99.0")
        self.assertEqual(custom_values["__metric_max__"], "100.0")
        self.assertEqual(custom_values["__metric_unit__"], "GiB")
        self.assertEqual(custom_values["__metric_state__"], "critical")
        self.assertEqual(custom_values["__metric_previous_state__"], "ok")
        self.assertEqual(custom_values["__metric_severity__"], "critical")
        self.assertEqual(custom_values["__server__"], self.server_test_1.reference)
        self.assertEqual(custom_values["__jet__"], "")

    def test_action_jet_runs_on_server(self):
        """A jet value runs the action on its server, with the jet."""
        with self._patch_run_command() as run_command_mock:
            metric_value = self.jet_sample.record_metric(
                "test_disk", used=95, total=100
            )
        server, _command = run_command_mock.call_args.args
        kwargs = run_command_mock.call_args.kwargs
        self.assertEqual(server, self.server_test_1)
        self.assertEqual(kwargs["jet"], self.jet_sample)
        self.assertEqual(kwargs["log"], {})
        self.assertEqual(kwargs["metric_value"], metric_value)
        self.assertEqual(
            kwargs["variable_values"]["__jet__"], self.jet_sample.reference
        )

    def test_action_plan_kwargs(self):
        """A plan action stores the metric on the plan log."""
        self.threshold_disk_critical.write(
            {"action": "plan", "command_id": False, "plan_id": self.plan_collect.id}
        )
        with self._patch_run_flight_plan() as run_flight_plan_mock:
            metric_value = self.jet_sample.record_metric(
                "test_disk", used=95, total=100
            )
        self.assertEqual(run_flight_plan_mock.call_count, 1)
        server, plan = run_flight_plan_mock.call_args.args
        kwargs = run_flight_plan_mock.call_args.kwargs
        self.assertEqual(server, self.server_test_1)
        self.assertEqual(plan, self.plan_collect)
        self.assertEqual(kwargs["jet"], self.jet_sample)
        self.assertEqual(
            kwargs["plan_log"],
            {"metric_id": self.metric_disk.id, "metric_value_id": metric_value.id},
        )
        self.assertNotIn("metric", kwargs)
        self.assertNotIn("metric_value", kwargs)
        self.assertEqual(set(kwargs["variable_values"]), CUSTOM_VALUE_KEYS)

    def test_action_none_runs_nothing(self):
        """Severity-only thresholds run nothing."""
        with (
            self._patch_run_command() as run_command_mock,
            self._patch_run_flight_plan() as run_flight_plan_mock,
        ):
            self.server_test_1.record_metric("test_disk", used=85, total=100)
        run_command_mock.assert_not_called()
        run_flight_plan_mock.assert_not_called()

    def test_command_eval_context(self):
        """A threshold Python command gets metric, metric_value and jet."""
        # Run in Odoo even if a deferral backend (queue, drone) is installed
        with self._patch_defer_handlers([]):
            metric_value = self.server_test_1.record_metric(
                "test_disk", used=95, total=100
            )
            jet_value = self.jet_sample.record_metric("test_disk", used=95, total=100)
        self.assertEqual(
            self._report_responses(self.command_report_metric),
            [
                f"test_disk|{metric_value.id}|None",
                f"test_disk|{jet_value.id}|{self.jet_sample.reference}",
            ],
        )

    def test_command_eval_context_without_metric(self):
        """A normal Python command gets metric and metric_value as None."""
        result = self.server_test_1.with_context(no_command_log=True).run_command(
            self.command_report_metric
        )
        self.assertEqual(result["response"], "None|None|None")

    def test_plan_eval_context_all_lines(self):
        """Every line of a threshold plan, nested plans too, sees the metric."""
        report_commands = self.Command
        for index in range(4):
            report_commands |= self.command_report_metric.copy(
                {"name": f"Test Report Metric {index}"}
            )
        child_plan = self.Plan.create(
            {
                "name": "Test Metric Child Plan",
                "line_ids": [
                    (0, 0, {"sequence": 10, "command_id": report_commands[2].id}),
                    (0, 0, {"sequence": 20, "command_id": report_commands[3].id}),
                ],
            }
        )
        command_run_child = self.Command.create(
            {
                "name": "Test Run Metric Child Plan",
                "action": "plan",
                "flight_plan_id": child_plan.id,
            }
        )
        parent_plan = self.Plan.create(
            {
                "name": "Test Metric Parent Plan",
                "line_ids": [
                    (0, 0, {"sequence": 10, "command_id": report_commands[0].id}),
                    (0, 0, {"sequence": 20, "command_id": report_commands[1].id}),
                    (0, 0, {"sequence": 30, "command_id": command_run_child.id}),
                ],
            }
        )
        self.threshold_disk_critical.write(
            {"action": "plan", "command_id": False, "plan_id": parent_plan.id}
        )

        # Run in Odoo even if a deferral backend (queue, drone) is installed
        with self._patch_defer_handlers([]):
            metric_value = self.jet_sample.record_metric(
                "test_disk", used=95, total=100
            )

        expected = f"test_disk|{metric_value.id}|{self.jet_sample.reference}"
        for command in report_commands:
            self.assertEqual(self._report_responses(command), [expected], command.name)

        child_log = self.PlanLog.search([("plan_id", "=", child_plan.id)])
        self.assertEqual(child_log.metric_id, self.metric_disk)
        self.assertEqual(child_log.metric_value_id, metric_value)
        self.assertTrue(child_log.parent_flight_plan_log_id)

    def test_stale_cron(self):
        """Stale values update the server and run stale thresholds once."""
        self.MetricThreshold.create(
            {
                "metric_id": self.metric_load.id,
                "condition": "stale",
                "action": "command",
                "command_id": self.command_report_metric.id,
            }
        )
        metric_value = self.server_test_1.record_metric("test_load", value=1)
        self.assertEqual(self.server_test_1.monitoring_state, "ok")

        # Not stale yet: nothing happens
        with self._patch_run_command() as run_command_mock:
            self.MetricValue._cron_check_stale()
        run_command_mock.assert_not_called()

        # Move the sample to the past without recomputing the state,
        # as the time passing would do
        self.env.cr.execute(
            "UPDATE cx_tower_metric_value "
            "SET last_update = now() at time zone 'UTC' - interval '2 hours' "
            "WHERE id = %s",
            (metric_value.id,),
        )
        metric_value.invalidate_recordset()
        self.server_test_1.invalidate_recordset()
        self.assertEqual(metric_value.state, "ok")

        with self._patch_run_command() as run_command_mock:
            self.MetricValue._cron_check_stale()
            self.MetricValue._cron_check_stale()
        self.assertEqual(metric_value.state, "stale")
        self.assertEqual(self.server_test_1.monitoring_state, "stale")
        self.assertEqual(run_command_mock.call_count, 1)
        kwargs = run_command_mock.call_args.kwargs
        self.assertEqual(kwargs["variable_values"]["__metric_state__"], "stale")
        self.assertEqual(kwargs["variable_values"]["__metric_previous_state__"], "ok")
        self.assertEqual(kwargs["variable_values"]["__metric_severity__"], "")

        # A fresh sample clears the stale threshold
        self.server_test_1.record_metric("test_load", value=1)
        self.assertEqual(metric_value.state, "ok")
        self.assertFalse(metric_value.active_threshold_ids)

    def test_stale_cron_after_shorter_interval(self):
        """A shorter stale interval makes the value stale at once.

        The stale threshold still runs on the next cron run, once.
        """
        stale_threshold = self.MetricThreshold.create(
            {
                "metric_id": self.metric_load.id,
                "condition": "stale",
                "action": "command",
                "command_id": self.command_report_metric.id,
            }
        )
        metric_value = self.server_test_1.record_metric("test_load", value=1)
        self._make_stale(metric_value, minutes=10)
        self.assertEqual(metric_value.state, "ok")

        # Recomputes the state without evaluating the thresholds
        self.metric_load.stale_after_minutes = 5
        self.assertEqual(metric_value.state, "stale")
        self.assertFalse(metric_value.active_threshold_ids)

        with self._patch_run_command() as run_command_mock:
            self.MetricValue._cron_check_stale()
            self.MetricValue._cron_check_stale()
        self.assertEqual(run_command_mock.call_count, 1)
        self.assertEqual(metric_value.active_threshold_ids, stale_threshold)

    def test_command_running_plan_sees_metric(self):
        """A threshold command that runs a flight plan passes the metric
        to every line of the flight plan."""
        report_commands = self.Command
        for index in range(2):
            report_commands |= self.command_report_metric.copy(
                {"name": f"Test Report Metric Via Command {index}"}
            )
        plan = self.Plan.create(
            {
                "name": "Test Metric Plan Via Command",
                "line_ids": [
                    (0, 0, {"sequence": 10, "command_id": report_commands[0].id}),
                    (0, 0, {"sequence": 20, "command_id": report_commands[1].id}),
                ],
            }
        )
        command_run_plan = self.Command.create(
            {
                "name": "Test Run Metric Plan",
                "action": "plan",
                "flight_plan_id": plan.id,
            }
        )
        self.threshold_disk_critical.command_id = command_run_plan

        # Run in Odoo even if a deferral backend (queue, drone) is installed
        with self._patch_defer_handlers([]):
            metric_value = self.jet_sample.record_metric(
                "test_disk", used=95, total=100
            )

        expected = f"test_disk|{metric_value.id}|{self.jet_sample.reference}"
        for command in report_commands:
            self.assertEqual(self._report_responses(command), [expected], command.name)
        plan_log = self.PlanLog.search([("plan_id", "=", plan.id)])
        self.assertEqual(plan_log.metric_id, self.metric_disk)
        self.assertEqual(plan_log.metric_value_id, metric_value)

    def test_stale_threshold_rearmed_by_longer_interval(self):
        """A value made fresh by a longer stale interval runs its stale
        threshold again when it becomes stale again."""
        stale_threshold = self.MetricThreshold.create(
            {
                "metric_id": self.metric_load.id,
                "condition": "stale",
                "action": "command",
                "command_id": self.command_report_metric.id,
            }
        )
        self.metric_load.stale_after_minutes = 30
        metric_value = self.server_test_1.record_metric("test_load", value=1)
        self._make_stale(metric_value, minutes=60)
        with self._patch_run_command() as run_command_mock:
            self.MetricValue._cron_check_stale()
        self.assertEqual(run_command_mock.call_count, 1)
        self.assertEqual(metric_value.active_threshold_ids, stale_threshold)

        # Fresh again: the stale threshold is cleared by the next check
        self.metric_load.stale_after_minutes = 120
        self.assertEqual(metric_value.state, "ok")
        with self._patch_run_command() as run_command_mock:
            self.MetricValue._cron_check_stale()
        run_command_mock.assert_not_called()
        self.assertFalse(metric_value.active_threshold_ids)

        # Stale again: the action runs again
        self.metric_load.stale_after_minutes = 30
        with self._patch_run_command() as run_command_mock:
            self.MetricValue._cron_check_stale()
        self.assertEqual(run_command_mock.call_count, 1)
        self.assertEqual(metric_value.active_threshold_ids, stale_threshold)
