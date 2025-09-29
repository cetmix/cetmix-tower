# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json
from datetime import datetime, timedelta

from .common import CetmixTowerWebhookCommon


class TestCetmixTowerWebhookLog(CetmixTowerWebhookCommon):
    def test_create_log_from_call(self):
        """Test creating a log entry via create_from_call()."""
        vals = {
            "result_message": "Manual log",
            "http_status": 201,
            "authentication_status": "success",
            "code_status": "success",
            "request_payload": json.dumps({"foo": "bar"}),
            "request_headers": json.dumps({"X-Test": "test"}),
            "webhook_id": self.simple_webhook.id,
        }
        log = self.Log.create_from_call(webhook=self.simple_webhook, **vals)
        self.assertEqual(log.webhook_id, self.simple_webhook)
        self.assertEqual(log.result_message, "Manual log")
        self.assertEqual(log.http_status, 201)
        self.assertEqual(log.authentication_status, "success")
        self.assertIn("foo", log.request_payload)
        self.assertIn("X-Test", log.request_headers)

    def test_gc_delete_old_logs(self):
        """Test auto-removal of old logs via _gc_delete_old_logs()."""
        # Create an "old" log
        old_log = self.Log.create_from_call(
            webhook=self.simple_webhook,
            authentication_status="success",
            code_status="success",
            http_status=200,
        )
        # Set create_date in the past (we cannot use write
        # because the create_date is MAGIC Field)
        past_date = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d %H:%M:%S")
        self.env.cr.execute(
            "UPDATE cx_tower_webhook_log SET create_date = %s WHERE id = %s",
            (past_date, old_log.id),
        )
        self.env.invalidate_all()
        # Create a new log
        new_log = self.Log.create_from_call(
            webhook=self.simple_webhook,
            authentication_status="success",
            code_status="success",
            http_status=200,
        )
        # Set log duration to 30 days
        self.env["ir.config_parameter"].sudo().set_param(
            "cetmix_tower_webhook.webhook_log_duration", 30
        )
        # Enter test mode to run the autovacuum cron because
        # `_run_vacuum_cleaner` makes a commit
        self.registry.enter_test_mode(self.cr)
        self.addCleanup(self.registry.leave_test_mode)
        env = self.env(cr=self.registry.cursor())

        # Run the autovacuum cron
        env.ref("base.autovacuum_job").method_direct_trigger()

        self.assertFalse(self.Log.browse(old_log.id).exists())
        self.assertTrue(self.Log.browse(new_log.id).exists())
