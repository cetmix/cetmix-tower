# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from .common import TestDroneCommon

RESULT = {"status": 0, "response": "output", "error": None}


class TestDroneCallback(TestDroneCommon):
    def test_callback_truthy(self):
        job = self.running_job()
        self.assertEqual(job._deliver("done", RESULT), "done")
        self.assertEqual(job.state, "done")
        self.assertTrue(job.date_done)
        self.assertEqual(job.callback_attempts, 1)
        self.assertEqual(len(self.callback_calls), 1)
        call = self.callback_calls[0]
        self.assertEqual(call["record"], self.target.id)
        self.assertEqual(call["job"], job.id)
        self.assertEqual(call["state"], "done")
        self.assertEqual(call["result"], RESULT)

    def test_callback_falsy(self):
        job = self.running_job()
        type(self).callback_mode = "falsy"
        self.assertEqual(job._deliver("done", RESULT), "retry")
        self.assertEqual(job.state, "running")
        self.assertFalse(job.date_done)
        self.assertEqual(job.callback_attempts, 1)

    def test_callback_raises(self):
        job = self.running_job()
        type(self).callback_mode = "raise"
        with self.assertLogs(
            "odoo.addons.cetmix_tower_drone.models.cx_tower_drone_job", "ERROR"
        ):
            self.assertEqual(job._deliver("done", RESULT), "retry")
        self.assertEqual(job.state, "running")
        self.assertEqual(job.callback_attempts, 1)
        self.assertEqual(
            job.callback_error,
            "ValueError in cx.tower.tag._test_drone_done, attempt 1",
        )
        # Never the exception message or any part of the result
        self.assertNotIn("secret", job.callback_error)
        self.assertNotIn("output", job.callback_error)

    def test_second_delivery_ignored(self):
        job = self.running_job()
        self.assertEqual(job._deliver("done", RESULT), "done")
        self.assertEqual(job._deliver("failed", RESULT), "ignored")
        self.assertEqual(len(self.callback_calls), 1)
        self.assertEqual(job.state, "done")

    def test_delivery_refreshes_heartbeat_even_on_retry(self):
        job = self.running_job()
        type(self).callback_mode = "falsy"
        job._deliver("done", RESULT)
        self.assertGreater(str(job.last_heartbeat), "2026-01-01 00:00:00")
        job.write({"last_heartbeat": "2026-01-01 00:00:00"})
        job._deliver("timed_out", None, from_controller=False)
        self.assertEqual(str(job.last_heartbeat), "2026-01-01 00:00:00")

    def test_method_removed(self):
        job = self.running_job()
        tag_class = type(self.Tag)
        original = tag_class._test_drone_done
        del tag_class._test_drone_done
        try:
            self.assertEqual(job._deliver("done", RESULT), "ignored")
        finally:
            tag_class._test_drone_done = original
        self.assertEqual(job.state, "failed")
        self.assertTrue(job.date_done)
        self.assertIn("cx.tower.tag._test_drone_done", job.callback_error)
        self.assertFalse(self.callback_calls)

    def test_target_deleted(self):
        target = self.Tag.create({"name": "Deleted Target"})
        job = self.running_job(target=target)
        target.unlink()
        self.assertEqual(job._deliver("done", RESULT), "ignored")
        self.assertEqual(job.state, "failed")
        self.assertFalse(self.callback_calls)

    def test_model_not_in_registry(self):
        job = self.running_job()
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE cx_tower_drone_job SET res_model = %s WHERE id = %s",
            ["cx.tower.uninstalled.model", job.id],
        )
        job.invalidate_recordset()
        self.assertEqual(job._deliver("done", RESULT), "ignored")
        self.assertEqual(job.state, "failed")
        self.assertFalse(self.callback_calls)

    def test_callback_runs_as_user(self):
        job = self.running_job(target=self.target.with_user(self.user_root))
        self.assertEqual(job.user_id, self.user_root)
        job._deliver("done", RESULT)
        self.assertEqual(self.callback_calls[0]["uid"], self.user_root.id)

    def test_pending_job_is_deliverable(self):
        job = self.launch().sudo()
        self.env.cr.postcommit.clear()
        self.assertEqual(job._deliver("failed", RESULT), "done")
        self.assertEqual(job.state, "failed")

    def test_lock_not_available_returns_retry(self):
        from psycopg2 import errors

        job = self.running_job()
        original_execute = type(self.env.cr).execute

        def execute(cr, query, *args, **kwargs):
            if "FOR UPDATE NOWAIT" in str(query):
                raise errors.LockNotAvailable()
            return original_execute(cr, query, *args, **kwargs)

        with patch.object(type(self.env.cr), "execute", execute):
            self.assertEqual(job._deliver("done", RESULT), "retry")
        self.assertEqual(job.state, "running")
        self.assertFalse(self.callback_calls)
