# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json

from odoo.tests import HttpCase, tagged

from .common import TestDroneCommon

RESULT_URL = "/cetmix_tower_drone/job/result"
HEARTBEAT_URL = "/cetmix_tower_drone/job/heartbeat"
STATUS_URL = "/cetmix_tower_drone/controller/status"


@tagged("post_install", "-at_install")
class TestDroneHttp(TestDroneCommon, HttpCase):
    def _post(self, url, data, key="response-Controller 1"):
        self.env.flush_all()
        response = self.url_open(
            url,
            data=json.dumps(data),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
        )
        self.env.invalidate_all()
        return response

    def _result(self, job, **vals):
        data = {
            "nonce": job.nonce,
            "state": "finished",
            "status": 0,
            "response": "ok",
            "error": None,
        }
        data.update(vals)
        return data

    # ------------------------------
    # Result
    # ------------------------------
    def test_result_delivered(self):
        job = self.running_job()
        response = self._post(RESULT_URL, self._result(job))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(job.state, "done")
        self.assertEqual(
            self.callback_calls[-1]["result"],
            {"status": 0, "response": "ok", "error": None},
        )

    def test_result_failed(self):
        job = self.running_job()
        response = self._post(RESULT_URL, self._result(job, state="failed"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(job.state, "failed")

    def test_result_unknown_nonce(self):
        self.running_job()
        response = self._post(RESULT_URL, {"nonce": "unknown", "state": "finished"})
        self.assertEqual(response.status_code, 404)

    def test_result_wrong_key(self):
        job = self.running_job()
        for key in ("wrong", "response-Controller 2", ""):
            response = self._post(RESULT_URL, self._result(job), key=key)
            self.assertEqual(response.status_code, 403)
            self.assertEqual(job.state, "running")
        self.assertFalse(self.callback_calls)

    def test_result_retry_503(self):
        job = self.running_job()
        type(self).callback_mode = "falsy"
        response = self._post(RESULT_URL, self._result(job))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(job.state, "running")
        self.assertEqual(job.callback_attempts, 1)

    def test_result_ignored_200(self):
        job = self.running_job()
        job._deliver("done", {"status": 0, "response": "", "error": None})
        response = self._post(RESULT_URL, self._result(job, state="failed"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(job.state, "done")

    def test_result_bad_request(self):
        job = self.running_job()
        response = self._post(RESULT_URL, self._result(job, state="weird"))
        self.assertEqual(response.status_code, 400)
        self.env.flush_all()
        response = self.url_open(RESULT_URL, data="not json")
        self.assertEqual(response.status_code, 400)

    # ------------------------------
    # Heartbeat
    # ------------------------------
    def test_heartbeat_running(self):
        job = self.running_job()
        response = self._post(HEARTBEAT_URL, {"nonce": job.nonce})
        self.assertEqual(response.status_code, 200)
        self.assertGreater(str(job.last_heartbeat), "2026-01-01 00:00:00")

    def test_heartbeat_pending_adopts(self):
        job = self.launch().sudo()
        self.env.cr.postcommit.clear()
        response = self._post(HEARTBEAT_URL, {"nonce": job.nonce})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(job.state, "running")
        self.assertTrue(job.last_heartbeat)

    def test_heartbeat_terminal_409(self):
        job = self.running_job()
        for state in ("done", "failed", "timed_out", "cancelled"):
            job.write({"state": state})
            response = self._post(HEARTBEAT_URL, {"nonce": job.nonce})
            self.assertEqual(response.status_code, 409)

    def test_heartbeat_auth(self):
        job = self.running_job()
        self.assertEqual(
            self._post(HEARTBEAT_URL, {"nonce": "unknown"}).status_code, 404
        )
        self.assertEqual(
            self._post(HEARTBEAT_URL, {"nonce": job.nonce}, key="wrong").status_code,
            403,
        )

    # ------------------------------
    # Controller status
    # ------------------------------
    def test_status(self):
        reference = self.controller_1.reference
        response = self._post(STATUS_URL, {"reference": reference, "status": "error"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.controller_1.status, "error")

    def test_status_cannot_set_draining(self):
        reference = self.controller_1.reference
        response = self._post(
            STATUS_URL, {"reference": reference, "status": "draining"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.controller_1.status, "available")

    def test_status_cannot_clear_draining(self):
        self.controller_1.status = "draining"
        reference = self.controller_1.reference
        response = self._post(
            STATUS_URL, {"reference": reference, "status": "available"}
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.controller_1.status, "draining")

    def test_status_wrong_key(self):
        reference = self.controller_1.reference
        response = self._post(
            STATUS_URL, {"reference": reference, "status": "error"}, key="wrong"
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.controller_1.status, "available")
