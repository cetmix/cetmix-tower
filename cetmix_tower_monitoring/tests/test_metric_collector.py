# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from .common import TestMonitoringCommon


class TestMetricCollector(TestMonitoringCommon):
    """Refresh, collector overrides and webhooks."""

    def test_refresh_runs_shared_collector_once(self):
        """A collector shared by two metrics runs once per server."""
        (self.metric_disk | self.metric_load).write(
            {"command_id": self.command_report_metric.id}
        )
        self.MetricValue.create(
            [
                {"metric_id": self.metric_disk.id, "server_id": self.server_test_1.id},
                {"metric_id": self.metric_load.id, "server_id": self.server_test_1.id},
            ]
        )
        self.assertTrue(self.server_test_1.has_metric_collector)

        with self._patch_run_command() as run_command_mock:
            self.server_test_1.action_refresh_metrics()
        self.assertEqual(run_command_mock.call_count, 1)
        server, command = run_command_mock.call_args.args
        kwargs = run_command_mock.call_args.kwargs
        self.assertEqual(server, self.server_test_1)
        self.assertEqual(command, self.command_report_metric)
        self.assertEqual(kwargs, {"jet": None, "log": {}})

    def test_refresh_jet(self):
        """A jet runs its collectors on its server, with the jet."""
        self.metric_load.write({"plan_id": self.plan_collect.id})
        self.MetricValue.create(
            {"metric_id": self.metric_load.id, "jet_id": self.jet_sample.id}
        )
        with (
            self._patch_run_command() as run_command_mock,
            self._patch_run_flight_plan() as run_flight_plan_mock,
        ):
            self.jet_sample.action_refresh_metrics()
        run_command_mock.assert_not_called()
        self.assertEqual(run_flight_plan_mock.call_count, 1)
        server, plan = run_flight_plan_mock.call_args.args
        self.assertEqual(server, self.server_test_1)
        self.assertEqual(plan, self.plan_collect)
        self.assertEqual(
            run_flight_plan_mock.call_args.kwargs, {"jet": self.jet_sample}
        )

    def test_refresh_without_collector(self):
        """Without a collector, Refresh is hidden and runs nothing."""
        self.server_test_1.record_metric("test_load", value=1)
        self.assertFalse(self.server_test_1.has_metric_collector)
        with (
            self._patch_run_command() as run_command_mock,
            self._patch_run_flight_plan() as run_flight_plan_mock,
        ):
            self.server_test_1.action_refresh_metrics()
        run_command_mock.assert_not_called()
        run_flight_plan_mock.assert_not_called()

    def test_collector_override(self):
        """A value collector replaces the metric collector."""
        self.metric_load.write({"command_id": self.command_create_dir.id})
        self.metric_disk.write({"command_id": self.command_create_dir.id})
        self.MetricValue.create(
            [
                {
                    "metric_id": self.metric_load.id,
                    "server_id": self.server_test_1.id,
                    "plan_id": self.plan_collect.id,
                },
                {
                    "metric_id": self.metric_disk.id,
                    "server_id": self.server_test_1.id,
                    "command_id": self.command_report_metric.id,
                },
            ]
        )
        with (
            self._patch_run_command() as run_command_mock,
            self._patch_run_flight_plan() as run_flight_plan_mock,
        ):
            self.server_test_1.action_refresh_metrics()
        self.assertEqual(run_command_mock.call_count, 1)
        self.assertEqual(run_command_mock.call_args.args[1], self.command_report_metric)
        self.assertEqual(run_flight_plan_mock.call_count, 1)
        self.assertEqual(run_flight_plan_mock.call_args.args[1], self.plan_collect)

    def test_python_collector_records_metrics(self):
        """A Python collector command records the metrics it names."""
        collector = self.Command.create(
            {
                "name": "Test Collector",
                "action": "python_code",
                "code": (
                    "server.record_metric('test_disk', used=40, total=80)\n"
                    "server.record_metric('test_load', value=0.5)\n"
                    "result = {'exit_code': 0, 'message': 'ok'}"
                ),
            }
        )
        (self.metric_disk | self.metric_load).write({"command_id": collector.id})
        self.MetricValue.create(
            {"metric_id": self.metric_disk.id, "server_id": self.server_test_1.id}
        )
        # Run in Odoo even if a deferral backend (queue, drone) is installed
        with self._patch_defer_handlers([]):
            self.server_test_1.action_refresh_metrics()
        values = self.server_test_1.metric_value_ids
        self.assertEqual(len(values), 2)
        disk_value = values.filtered(lambda v: v.metric_id == self.metric_disk)
        self.assertEqual((disk_value.value, disk_value.max_value), (40, 80))
        load_value = values.filtered(lambda v: v.metric_id == self.metric_load)
        self.assertEqual(load_value.value, 0.5)

    def test_webhook_records_metric(self):
        """Webhook code resolves the server and records the metrics."""
        authenticator = self.env["cx.tower.webhook.authenticator"].create(
            {"name": "Test Metric Authenticator", "code": "result = {'allowed': True}"}
        )
        webhook = self.env["cx.tower.webhook"].create(
            {
                "name": "Test Metric Webhook",
                "endpoint": "test_metric_webhook",
                "authenticator_id": authenticator.id,
                "code": (
                    "server = tower_servers.get_by_reference("
                    "payload['server_reference'])\n"
                    "for item in payload['metrics']:\n"
                    "    server.record_metric(item['reference'], "
                    "value=item.get('value'), used=item.get('used'), "
                    "total=item.get('total'))\n"
                    "result = {'exit_code': 0, 'message': 'ok'}"
                ),
            }
        )
        result = webhook.execute(
            {
                "server_reference": self.server_test_1.reference,
                "metrics": [
                    {"reference": "test_disk", "used": 45.2, "total": 100.0},
                    {"reference": "test_load", "value": 1.37},
                ],
            }
        )
        self.assertEqual(result["exit_code"], 0, result)
        values = self.server_test_1.metric_value_ids
        self.assertEqual(
            values.mapped("metric_id"), self.metric_disk | self.metric_load
        )

    def test_webhook_eval_context_has_no_metric(self):
        """Webhook help and eval context have no current metric."""
        for model_name in ("cx.tower.webhook", "cx.tower.webhook.authenticator"):
            model = self.env[model_name]
            help_text = model._default_eval_code_help()
            self.assertNotIn("<code>metric</code>", help_text)
            self.assertNotIn("<code>metric_value</code>", help_text)
            self.assertIn("<code>tower_metrics</code>", help_text)
            eval_context = model._prepare_webhook_eval_context()
            self.assertNotIn("metric", eval_context)
            self.assertNotIn("metric_value", eval_context)
            self.assertEqual(eval_context["tower_metrics"], self.Metric)

        # Commands list them
        command_help = self.Command._get_default_python_code_help()
        self.assertIn("<code>metric</code>", command_help)
        self.assertIn("<code>metric_value</code>", command_help)
        self.assertIn("<code>tower_metric_values</code>", command_help)

    def test_settings_cron_actions(self):
        """The Monitoring settings open the monitoring cron jobs."""
        settings = self.env["res.config.settings"].create({})
        for method, cron_xml_id in (
            (
                "action_configure_metric_stale_cron",
                "ir_cron_cx_tower_metric_value_check_stale",
            ),
            (
                "action_configure_metric_auto_sync_cron",
                "ir_cron_cx_tower_metric_value_auto_sync",
            ),
        ):
            action = getattr(settings, method)()
            self.assertEqual(action["res_model"], "ir.cron")
            self.assertEqual(
                action["res_id"],
                self.env.ref(f"cetmix_tower_monitoring.{cron_xml_id}").id,
            )
