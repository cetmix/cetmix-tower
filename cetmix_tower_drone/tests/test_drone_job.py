# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import contextlib
import json
from datetime import timedelta
from unittest.mock import patch

import requests
from cryptography.fernet import Fernet
from psycopg2 import errors

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.sql_db import TestCursor
from odoo.tools import mute_logger

from ..models.cx_tower_drone_job import CxTowerDroneJob
from .common import JOB_LOGGER, TestDroneCommon, connection_refused


class _Rollback(Exception):
    pass


class TestDroneJob(TestDroneCommon):
    # ------------------------------
    # launch_drone() validation
    # ------------------------------
    def test_launch_unknown_skill_returns_empty(self):
        """A skill no controller advertised creates no job."""
        before = self.Job.search_count([])
        job = self.launch(skill="no_such_skill")
        self.assertFalse(job)
        self.assertEqual(job._name, "cx.tower.drone.job")
        self.assertEqual(self.Job.search_count([]), before)

    def test_launch_rejects_non_bound_callbacks(self):
        def plain_function(drone_job, result):
            return True

        def make_closure():
            record = self.target

            def closure(drone_job, result):
                return record

            return closure

        for callback in (lambda job, result: True, make_closure(), plain_function):
            with self.assertRaises(ValidationError):
                self.target.launch_drone("test_skill", callback, {})

    def test_launch_several_records(self):
        """Several records are one job, stored in recordset order, called once."""
        records = self.Tag.browse([self.tag_b.id, self.tag_a.id])
        job = records.launch_drone("test_skill", records._test_drone_done, {}).sudo()
        self.assertEqual(job.res_ids, [self.tag_b.id, self.tag_a.id])
        self.env.cr.postcommit.clear()
        self.assertEqual(
            job._deliver("done", {"status": 0, "response": "", "error": None}),
            "done",
        )
        self.assertEqual(len(self.callback_calls), 1)
        self.assertEqual(
            self.callback_calls[0]["record"], [self.tag_b.id, self.tag_a.id]
        )

    def test_launch_without_ids(self):
        """No ids: the callback runs once on the model."""
        model = self.env["cx.tower.tag"]
        self.assertEqual(model._test_drone_model_done._api, "model")
        job = model.launch_drone("test_skill", model._test_drone_model_done, {}).sudo()
        self.assertFalse(job.res_ids)
        self.env.cr.postcommit.clear()
        self.assertEqual(
            job._deliver("done", {"status": 0, "response": "", "error": None}),
            "done",
        )
        self.assertEqual(job.state, "done")
        self.assertEqual(len(self.callback_calls), 1)
        self.assertEqual(self.callback_calls[0]["record"], [])
        self.assertEqual(self.callback_calls[0]["uid"], self.env.uid)

    def test_launch_rejects_new_records(self):
        """A new record is rejected before a controller is reserved."""
        cases = (
            self.Tag.new({"name": "New"}),
            self.target | self.Tag.new({}),
            self.Tag.new({}, origin=self.target),
        )
        for records in cases:
            jobs_before = self.Job.search([])
            reserved = (
                self.controller_1.sudo().reservation_seq,
                self.controller_2.sudo().reservation_seq,
            )
            with self.assertRaises(ValidationError):
                records.launch_drone("test_skill", records._test_drone_done, {})
            self.assertEqual(self.Job.search([]), jobs_before)
            self.assertEqual(
                (
                    self.controller_1.sudo().reservation_seq,
                    self.controller_2.sudo().reservation_seq,
                ),
                reserved,
            )

    def test_launch_rejects_payload_and_timeout(self):
        """A bad payload or timeout is rejected before a job exists."""
        before = self.Job.search_count([])
        payloads = (
            ["not", "a", "dict"],
            {"value": float("nan")},
            {"value": float("inf")},
            {"value": {1, 2}},
        )
        for payload in payloads:
            with self.assertRaises(ValidationError):
                self.launch(payload=payload)
        for timeout in (True, -1):
            with self.assertRaises(ValidationError):
                self.launch(timeout=timeout)
        self.assertEqual(self.Job.search_count([]), before)
        job = self.launch(timeout=0).sudo()
        self.assertEqual(job.timeout, 0)

    def test_launch_accepts_any_model(self):
        """A model with no mixin and no registration can be the target."""
        partner = self.env["res.partner"].create({"name": "Drone Partner"})

        def _drone_partner_done(self, drone_job, result):
            return True

        with patch.object(
            type(partner), "_drone_partner_done", _drone_partner_done, create=True
        ):
            job = partner.launch_drone(
                "test_skill",
                partner._drone_partner_done,
                {},
            )
        self.assertEqual(len(job), 1)
        self.assertEqual(job.res_model, "res.partner")
        self.assertEqual(job.res_ids, [partner.id])
        self.assertEqual(job.method_name, "_drone_partner_done")

    def test_launch_stores_callback_and_nothing_else(self):
        job = self.launch(payload={"echo": "secret param"}).sudo()
        self.assertEqual(job.res_model, "cx.tower.tag")
        self.assertEqual(job.res_ids, [self.target.id])
        self.assertEqual(job.method_name, "_test_drone_done")
        self.assertEqual(job.user_id.id, self.env.uid)
        self.assertEqual(job.timeout, 60)
        for field_name in ("params", "payload", "response", "result", "error"):
            self.assertNotIn(field_name, job._fields)
        stored = json.dumps(job.read()[0], default=str)
        self.assertNotIn("secret param", stored)

    def test_callback_fields_cannot_be_written(self):
        job = self.launch().sudo()
        for vals in (
            {"res_model": "res.partner"},
            {"res_ids": [1]},
            {"method_name": "unlink"},
            {"user_id": self.user_root.id},
        ):
            with self.assertRaises(AccessError):
                job.write(vals)

    # ------------------------------
    # Selection
    # ------------------------------
    def test_selection_by_priority(self):
        job = self.launch()
        self.assertEqual(job.sudo().controller_id, self.controller_1)
        self.controller_1.priority = 5
        self.controller_2.priority = 1
        job = self.launch()
        self.assertEqual(job.sudo().controller_id, self.controller_2)

    def test_selection_by_skill(self):
        self.controller_1.skill_ids = [(6, 0, [self.skill_untagged.id])]
        job = self.launch()
        self.assertEqual(job.sudo().controller_id, self.controller_2)

    def test_selection_skips_inactive_unavailable_draining(self):
        for vals in ({"active": False}, {"status": "error"}, {"status": "draining"}):
            self.controller_1.write(vals)
            job = self.launch()
            self.assertEqual(job.sudo().controller_id, self.controller_2)
            self.controller_1.write({"active": True, "status": "available"})

    def test_selection_max_running_jobs(self):
        self.controller_1.max_running_jobs = 1
        first = self.launch()
        self.assertEqual(first.sudo().controller_id, self.controller_1)
        second = self.launch()
        self.assertEqual(second.sudo().controller_id, self.controller_2)
        self.controller_2.max_running_jobs = 1
        self.assertFalse(self.launch())

    def test_selection_ignores_tags(self):
        """A controller with tags is still selected when it has the skill."""
        self.controller_1.tag_ids = [(6, 0, [self.tag_a.id])]
        self.controller_2.tag_ids = [(6, 0, [self.tag_b.id])]
        job = self.launch().sudo()
        self.assertEqual(job.controller_id, self.controller_1)

    def test_no_candidate(self):
        self.Controller.search([]).write({"status": "not_reachable"})
        callbacks_before = len(self.env.cr.postcommit)
        job = self.launch()
        self.assertFalse(job)
        self.assertEqual(job._name, "cx.tower.drone.job")
        self.assertFalse(self.Job.search([]))
        self.assertEqual(len(self.env.cr.postcommit), callbacks_before)

    def test_candidate_creates_pending_job_without_post(self):
        job = self.launch().sudo()
        self.assertEqual(job.state, "pending")
        self.assertFalse(job.last_heartbeat)
        self.assertFalse(self.network.calls)

    def test_rollback_after_launch_sends_nothing(self):
        with self.registry.cursor() as cr:
            env = self.env(cr=cr)
            target = self.target.with_env(env)
            job = target.launch_drone(
                "test_skill",
                target._test_drone_done,
                {},
            )
            self.assertTrue(job)
            self.assertEqual(len(cr.postcommit), 1)
            cr.rollback()
            self.assertFalse(len(cr.postcommit))
            self.assertFalse(env["cx.tower.drone.job"].sudo().search([]))
        self.assertFalse(self.network.calls)

    def test_concurrent_reservation(self):
        """Two dispatches against max_running_jobs = 1 never both reserve.

        Test cursors share one connection, so the second dispatch sees the
        first reservation and finds no candidate.
        """
        self.controller_1.max_running_jobs = 1
        self.controller_2.active = False
        self.env.flush_all()
        results = []
        for __ in range(2):
            with self.registry.cursor() as cr:
                target = self.target.with_env(self.env(cr=cr))
                results.append(
                    target.launch_drone(
                        "test_skill",
                        target._test_drone_done,
                        {},
                    ).ids
                )
        self.assertTrue(results[0])
        self.assertFalse(results[1])
        self.env.invalidate_all()
        self.assertEqual(
            self.Job.search_count(
                [
                    ("controller_id", "=", self.controller_1.id),
                    ("state", "=", "pending"),
                ]
            ),
            1,
        )

    # ------------------------------
    # Submission
    # ------------------------------
    def test_submission_accepted(self):
        job = self.launch(payload={"echo": "hello"}).sudo()
        self.run_postcommit()
        self.assertEqual(job.state, "running")
        self.assertEqual(job.controller_id, self.controller_1)
        self.assertTrue(job.last_heartbeat)
        posts = self.network.find("POST", "/jobs")
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["base"], self.controller_1.controller_url)

    def test_payload_encrypted_per_candidate(self):
        """``data`` is the same dict for every controller; the token is not."""
        self.network.set(self.controller_1, post=400)
        payload = {"echo": "hello"}
        job = self.launch(payload=payload).sudo()
        self.run_postcommit()
        posts = self.network.find("POST", "/jobs")
        self.assertEqual(len(posts), 2)
        tokens = []
        for post, controller in zip(
            posts, (self.controller_1, self.controller_2), strict=True
        ):
            self.assertEqual(list(post["json"]), ["payload"])
            tokens.append(post["json"]["payload"])
            key = controller.sudo()._get_secret_value("payload_key")
            envelope = json.loads(
                Fernet(key.encode()).decrypt(post["json"]["payload"].encode())
            )
            self.assertEqual(envelope["nonce"], job.nonce)
            self.assertEqual(envelope["skill"], "test_skill")
            self.assertEqual(envelope["timeout"], 60)
            self.assertEqual(
                envelope["callback_url"],
                "https://tower.example.com/cetmix_tower_drone/job/result",
            )
            self.assertEqual(
                envelope["heartbeat_url"],
                "https://tower.example.com/cetmix_tower_drone/job/heartbeat",
            )
            self.assertEqual(envelope["data"], payload)
            self.assertNotIn(
                controller.sudo()._get_secret_value("drone_api_key"),
                json.dumps(envelope),
            )
        self.assertNotEqual(tokens[0], tokens[1])

    @mute_logger(JOB_LOGGER)
    def test_submission_connection_refused_fails_over(self):
        self.network.set(self.controller_1, post=connection_refused())
        job = self.launch().sudo()
        self.run_postcommit()
        self.assertEqual(self.controller_1.status, "not_reachable")
        self.assertEqual(job.state, "running")
        self.assertEqual(job.controller_id, self.controller_2)

    def test_submission_4xx_fails_over(self):
        self.network.set(self.controller_1, post=422)
        job = self.launch().sudo()
        self.run_postcommit()
        self.assertEqual(self.controller_1.status, "error")
        self.assertEqual(job.controller_id, self.controller_2)
        self.assertEqual(job.state, "running")

    @mute_logger(JOB_LOGGER)
    def test_submission_all_rejected(self):
        self.network.set(self.controller_1, post=connection_refused())
        self.network.set(self.controller_2, post=400)
        job = self.launch().sudo()
        self.run_postcommit()
        self.assertEqual(job.state, "failed")
        self.assertEqual(len(self.callback_calls), 1)
        self.assertEqual(self.callback_calls[0]["state"], "failed")
        self.assertEqual(
            self.callback_calls[0]["result"]["error"],
            "No drone controller accepted the job",
        )

    def test_failover_commits_controller_before_post(self):
        self.network.set(self.controller_1, post=400)
        job = self.launch().sudo()
        events = []
        original_commit = TestCursor.commit

        def commit(cr):
            events.append("commit")
            return original_commit(cr)

        def post_to_second(method, path, payload):
            self.env.cr.execute(
                "SELECT controller_id FROM cx_tower_drone_job WHERE id = %s",
                [job.id],
            )
            events.append(("post", self.env.cr.fetchone()[0]))
            return 201

        self.network.set(self.controller_2, post=post_to_second)
        with patch.object(TestCursor, "commit", commit):
            self.run_postcommit()
        index = events.index(("post", self.controller_2.id))
        self.assertEqual(events[index - 1], "commit")

    def test_failover_respects_capacity(self):
        self.network.set(self.controller_1, post=400)
        self.controller_2.max_running_jobs = 1
        other = self.launch().sudo()
        self.make_running(other, self.controller_2)
        self.env.cr.postcommit.clear()
        job = self.launch().sudo()
        self.run_postcommit()
        self.assertFalse(
            self.network.find("POST", "/jobs", base=self.controller_2.controller_url)
        )
        self.assertEqual(job.state, "failed")

    def test_resubmission_excludes_the_job_itself(self):
        self.controller_1.max_running_jobs = 1
        job = self.launch().sudo()
        self.run_postcommit()
        self.assertEqual(job.state, "running")
        self.assertEqual(job.controller_id, self.controller_1)

    @mute_logger(JOB_LOGGER)
    def test_ambiguous_found_on_get(self):
        self.network.set(
            self.controller_1,
            post=requests.exceptions.ReadTimeout(),
            get=(200, {"state": "running"}),
        )
        job = self.launch().sudo()
        self.run_postcommit()
        self.assertEqual(job.state, "running")
        self.assertEqual(job.controller_id, self.controller_1)
        self.assertEqual(len(self.network.find("POST", "/jobs")), 1)

    def test_ambiguous_404_fenced_tries_next(self):
        self.network.set(self.controller_1, post=503, get=404)
        job = self.launch().sudo()
        self.run_postcommit()
        self.assertEqual(len(self.network.find("POST", "/fence")), 1)
        self.assertFalse(self.network.find("POST", "/cancel"))
        self.assertEqual(self.controller_1.status, "error")
        self.assertEqual(job.controller_id, self.controller_2)
        self.assertEqual(job.state, "running")

    def test_ambiguous_404_fence_accepted(self):
        self.network.set(
            self.controller_1, post=503, get=404, fence=(200, {"state": "accepted"})
        )
        job = self.launch().sudo()
        self.run_postcommit()
        self.assertEqual(job.state, "running")
        self.assertEqual(job.controller_id, self.controller_1)
        self.assertFalse(
            self.network.find("POST", "/jobs", base=self.controller_2.controller_url)
        )
        self.assertFalse(self.network.find("POST", "/cancel"))

    def test_ambiguous_404_fence_fails(self):
        for fence in (requests.exceptions.ReadTimeout(), (200, {"state": "?"}), 500):
            self.network.reset()
            self.network.set(self.controller_1, post=503, get=404, fence=fence)
            job = self.launch().sudo()
            self.run_postcommit()
            self.assertEqual(job.state, "running")
            self.assertEqual(job.controller_id, self.controller_1)
            self.assertFalse(
                self.network.find(
                    "POST", "/jobs", base=self.controller_2.controller_url
                )
            )
            self.controller_1.status = "available"

    @mute_logger(JOB_LOGGER)
    def test_errors_after_sending_are_ambiguous(self):
        """Errors raised while reading the response: reconcile, no failover."""
        for exc in (
            requests.exceptions.SSLError(),
            requests.exceptions.InvalidHeader(),
        ):
            self.network.reset()
            self.network.set(
                self.controller_1, post=exc, get=(200, {"state": "running"})
            )
            job = self.launch().sudo()
            self.run_postcommit()
            self.assertEqual(len(self.network.find("GET", f"/jobs/{job.nonce}")), 1)
            self.assertEqual(job.state, "running")
            self.assertEqual(job.controller_id, self.controller_1)
            self.assertFalse(
                self.network.find(
                    "POST", "/jobs", base=self.controller_2.controller_url
                )
            )

    def test_redirect_is_ambiguous(self):
        """A redirect is not followed and not taken as a rejection."""
        self.network.set(self.controller_1, post=307, get=(200, {"state": "running"}))
        job = self.launch().sudo()
        self.run_postcommit()
        self.assertEqual(len(self.network.find("GET", f"/jobs/{job.nonce}")), 1)
        self.assertEqual(job.state, "running")
        self.assertEqual(job.controller_id, self.controller_1)
        self.assertFalse(
            self.network.find("POST", "/jobs", base=self.controller_2.controller_url)
        )

    @mute_logger(JOB_LOGGER)
    def test_ambiguous_again(self):
        self.network.set(
            self.controller_1,
            post=requests.exceptions.ReadTimeout(),
            get=requests.exceptions.ReadTimeout(),
        )
        job = self.launch().sudo()
        self.run_postcommit()
        self.assertEqual(job.state, "running")
        self.assertTrue(job.last_heartbeat)
        self.assertEqual(job.controller_id, self.controller_1)
        self.assertEqual(self.controller_1.status, "error")
        self.assertEqual(len(self.network.find("POST", "/jobs")), 1)
        self.assertFalse(self.callback_calls)

    def test_unresolved_submission_decided_by_poll(self):
        self.network.set(self.controller_1, post=503, get=503)
        job = self.launch().sudo()
        self.run_postcommit()
        self.assertEqual(job.state, "running")
        self.network.set(self.controller_1, get=404)
        self.Job._cron_poll()
        self.assertEqual(job.state, "failed")
        self.assertEqual(
            self.callback_calls[-1]["result"]["error"],
            "Job not found on the controller",
        )

        self.controller_1.status = "available"
        job = self.launch().sudo()
        self.network.set(self.controller_1, get=503)
        self.run_postcommit()
        self.network.set(
            self.controller_1,
            get=(200, {"state": "finished", "status": 0, "response": "ok"}),
        )
        self.Job._cron_poll()
        self.assertEqual(job.state, "done")
        self.assertEqual(self.callback_calls[-1]["result"]["response"], "ok")

    def test_early_result_wins_before_submission(self):
        """A result delivered while pending wins; submission writes nothing."""
        job = self.launch().sudo()
        self.assertEqual(
            job._deliver("done", {"status": 0, "response": "", "error": None}), "done"
        )
        self.run_postcommit()
        self.assertEqual(job.state, "done")
        self.assertFalse(self.network.find("POST", "/jobs"))

    def test_result_between_post_and_record(self):
        job = self.launch().sudo()

        def post(method, path, payload):
            job.invalidate_recordset()
            job._deliver("done", {"status": 0, "response": "", "error": None})
            self.env.flush_all()
            return 201

        self.network.set(self.controller_1, post=post)
        self.run_postcommit()
        self.assertEqual(job.state, "done")
        self.assertEqual(len(self.callback_calls), 1)

    def test_serialization_failure_in_claim_is_retried(self):
        controller_class = type(self.Controller)
        original = controller_class._reserve
        calls = []

        def flaky_reserve(controller, job=None):
            calls.append(controller.id)
            if len(calls) == 1:
                raise errors.SerializationFailure()
            return original(controller, job=job)

        job = self.launch().sudo()
        with patch.object(controller_class, "_reserve", flaky_reserve):
            self.run_postcommit()
        self.assertEqual(len(calls), 2)
        self.assertEqual(job.state, "running")
        self.assertEqual(len(self.network.find("POST", "/jobs")), 1)

    @mute_logger(JOB_LOGGER)
    def test_serialization_failure_after_post_never_resends(self):
        job = self.launch().sudo()
        original_write = CxTowerDroneJob.write

        def failing_write(records, vals):
            if vals.get("state") == "running":
                raise errors.SerializationFailure()
            return original_write(records, vals)

        with patch.object(CxTowerDroneJob, "write", failing_write):
            self.run_postcommit()
        self.assertEqual(job.state, "pending")
        self.assertEqual(len(self.network.find("POST", "/jobs")), 1)

        # The stale-pending sweep then asks the controller
        self._age(job)
        self.network.set(self.controller_1, get=(200, {"state": "running"}))
        self.Job._cron_check_timeout()
        self.assertEqual(job.state, "running")

    def test_nothing_escapes_postcommit(self):
        self.launch()
        with (
            patch.object(CxTowerDroneJob, "_submit", side_effect=RuntimeError("boom")),
            self.assertLogs(
                "odoo.addons.cetmix_tower_drone.models.cx_tower_drone_job", "ERROR"
            ),
        ):
            self.run_postcommit()

    @mute_logger(JOB_LOGGER)
    def test_controller_raising_leaves_reconcilable_job(self):
        self.network.set(self.controller_1, post=RuntimeError("boom"), get=500)
        job = self.launch().sudo()
        self.run_postcommit()
        self.assertEqual(job.state, "running")
        self.assertEqual(job.controller_id, self.controller_1)

    # ------------------------------
    # Cancel
    # ------------------------------
    def test_cancel_running(self):
        job = self.launch().sudo()
        self.run_postcommit()
        job._cancel()
        self.assertEqual(job.state, "cancelled")
        self.assertTrue(job.date_done)
        self.assertFalse(self.network.find("POST", "/cancel"))
        self.run_postcommit()
        self.assertEqual(len(self.network.find("POST", "/cancel")), 1)
        self.assertFalse(self.callback_calls)

    @mute_logger(JOB_LOGGER)
    def test_cancel_http_error_does_not_raise(self):
        job = self.launch().sudo()
        self.run_postcommit()
        for answer in (500, connection_refused()):
            self.network.set(self.controller_1, cancel=answer)
            job.sudo().write({"state": "running"})
            job._cancel()
            self.run_postcommit()
            self.assertEqual(job.state, "cancelled")

    def test_cancel_pending(self):
        """Cancelling a pending job fences it and stops the submission."""
        job = self.launch().sudo()
        job._cancel()
        self.run_postcommit()
        self.assertEqual(len(self.network.find("POST", "/cancel")), 1)
        self.assertFalse(self.network.find("POST", "/jobs"))
        self.assertEqual(job.state, "cancelled")

    def test_cancel_racing_submission(self):
        # The fence reached the controller: the POST is answered 409
        job = self.launch().sudo()

        def post_rejected(method, path, payload):
            job.invalidate_recordset()
            job._cancel()
            self.env.flush_all()
            return 409

        self.network.set(self.controller_1, post=post_rejected)
        self.run_postcommit()
        self.assertEqual(job.state, "cancelled")
        self.assertFalse(
            self.network.find("POST", "/jobs", base=self.controller_2.controller_url)
        )
        # Only the cancel registered by _cancel() itself
        self.assertEqual(len(self.network.find("POST", "/cancel")), 1)
        self.assertEqual(self.controller_1.status, "available")

        # The fence never arrived and the POST was accepted: cancel again
        self.network.reset()
        job = self.launch().sudo()

        def post_accepted(method, path, payload):
            job.invalidate_recordset()
            job._cancel()
            self.env.flush_all()
            return 201

        self.network.set(self.controller_1, post=post_accepted)
        self.run_postcommit()
        self.assertEqual(job.state, "cancelled")
        # The deferred cancel of _cancel() plus the one sent by the submission
        self.assertEqual(len(self.network.find("POST", "/cancel")), 2)

    def test_cancel_not_sent_before_commit(self):
        job = self.launch().sudo()
        self.run_postcommit()
        self.env.flush_all()
        # Transaction rolled back: nothing sent
        with self.registry.cursor() as cr:
            cr_job = job.with_env(self.env(cr=cr))
            cr_job._cancel()
            self.assertEqual(len(cr.postcommit), 1)
            cr.rollback()
            self.assertFalse(len(cr.postcommit))
        self.env.invalidate_all()
        self.assertEqual(job.state, "running")
        self.assertFalse(self.network.find("POST", "/cancel"))

        # Savepoint rolled back, outer transaction committed: nothing sent
        with contextlib.suppress(_Rollback), self.env.cr.savepoint():
            job._cancel()
            raise _Rollback()
        self.env.invalidate_all()
        self.run_postcommit()
        self.assertEqual(job.state, "running")
        self.assertFalse(self.network.find("POST", "/cancel"))

    # ------------------------------
    # Timeout cron
    # ------------------------------
    def _age(self, job, minutes=20):
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE cx_tower_drone_job SET create_date = %s WHERE id = %s",
            [fields.Datetime.now() - timedelta(minutes=minutes), job.id],
        )
        self.env.invalidate_all()

    def test_timeout_young_pending_untouched(self):
        job = self.launch().sudo()
        self.env.cr.postcommit.clear()
        self.Job._cron_check_timeout()
        self.assertEqual(job.state, "pending")
        self.assertFalse(self.network.calls)

    @mute_logger(JOB_LOGGER)
    def test_timeout_stale_pending(self):
        job = self.launch().sudo()
        self.env.cr.postcommit.clear()
        self._age(job)

        self.network.set(self.controller_1, get=requests.exceptions.ConnectTimeout())
        self.Job._cron_check_timeout()
        self.assertEqual(job.state, "pending")

        self.network.set(self.controller_1, get=(200, {"state": "running"}))
        self.Job._cron_check_timeout()
        self.assertEqual(job.state, "running")
        self.assertTrue(job.last_heartbeat)

        job = self.launch().sudo()
        self.env.cr.postcommit.clear()
        self._age(job)
        self.network.set(self.controller_1, get=404)
        self.Job._cron_check_timeout()
        self.assertEqual(job.state, "failed")
        self.assertEqual(
            self.callback_calls[-1]["result"]["error"],
            "Job was not submitted to any controller",
        )

    def test_heartbeat_timeout(self):
        job = self.launch().sudo()
        self.run_postcommit()
        # Fresh heartbeat: untouched
        self.Job._cron_check_timeout()
        self.assertEqual(job.state, "running")
        # Stale heartbeat: timed out, one cancel after commit
        job.write({"last_heartbeat": fields.Datetime.now() - timedelta(minutes=5)})
        self.Job._cron_check_timeout()
        self.assertEqual(job.state, "timed_out")
        self.assertEqual(self.callback_calls[-1]["state"], "timed_out")
        self.assertIsNone(self.callback_calls[-1]["result"])
        self.assertFalse(self.network.find("POST", "/cancel"))
        self.run_postcommit()
        self.assertEqual(len(self.network.find("POST", "/cancel")), 1)

    def test_heartbeat_timeout_rolled_back_sends_nothing(self):
        job = self.launch().sudo()
        self.run_postcommit()
        job.write({"last_heartbeat": fields.Datetime.now() - timedelta(minutes=5)})
        self.env.flush_all()
        with self.registry.cursor() as cr:
            self.Job.with_env(self.env(cr=cr))._cron_check_timeout()
            self.assertEqual(len(cr.postcommit), 1)
            cr.rollback()
        self.env.invalidate_all()
        self.assertEqual(job.state, "running")
        self.assertFalse(self.network.find("POST", "/cancel"))

    def test_heartbeat_timeout_zero_timeout(self):
        job = self.launch(timeout=0).sudo()
        self.run_postcommit()
        job.write({"last_heartbeat": fields.Datetime.now() - timedelta(days=5)})
        self.Job._cron_check_timeout()
        self.assertEqual(job.state, "running")

    @mute_logger(JOB_LOGGER)
    def test_heartbeat_timeout_no_cancel_on_retry_or_ignored(self):
        job = self.launch().sudo()
        self.run_postcommit()
        job.write({"last_heartbeat": fields.Datetime.now() - timedelta(minutes=5)})
        for result in ("retry", "ignored"):
            with patch.object(CxTowerDroneJob, "_deliver", return_value=result):
                funcs_before = len(self.env.cr.postcommit)
                self.Job._cron_check_timeout()
                self.assertEqual(len(self.env.cr.postcommit), funcs_before)
        self.assertEqual(job.state, "running")

    def test_timeout_guard_heartbeat_moved(self):
        job = self.launch().sudo()
        self.run_postcommit()
        stale = fields.Datetime.now() - timedelta(minutes=5)
        job.write({"last_heartbeat": stale})
        self.env.flush_all()
        self.assertEqual(
            job._deliver(
                "timed_out",
                None,
                from_controller=False,
                expect_heartbeat_before=stale - timedelta(seconds=1),
            ),
            "ignored",
        )
        self.assertEqual(job.state, "running")

    # ------------------------------
    # Poll
    # ------------------------------
    def test_poll(self):
        job = self.launch().sudo()
        self.run_postcommit()
        job.write({"last_heartbeat": "2026-01-01 00:00:00"})
        self.Job._cron_poll()
        self.assertGreater(
            job.last_heartbeat, fields.Datetime.to_datetime("2026-01-01")
        )

        self.network.set(
            self.controller_1,
            get=(200, {"state": "finished", "status": 0, "response": "out"}),
        )
        self.Job._cron_poll()
        self.assertEqual(job.state, "done")
        self.assertEqual(
            self.callback_calls[-1]["result"],
            {"status": 0, "response": "out", "error": None},
        )

        job = self.launch().sudo()
        self.network.set(self.controller_1, get=(200, {"state": "running"}))
        self.run_postcommit()
        self.network.set(
            self.controller_1, get=(200, {"state": "failed", "error": "e"})
        )
        self.Job._cron_poll()
        self.assertEqual(job.state, "failed")
        self.assertEqual(
            self.callback_calls[-1]["result"],
            {"status": None, "response": None, "error": "e"},
        )

    def test_poll_connection_error_skips(self):
        job = self.launch().sudo()
        self.run_postcommit()
        self.network.set(self.controller_1, get=connection_refused())
        self.Job._cron_poll()
        self.assertEqual(job.state, "running")

    # ------------------------------
    # Cron batches
    # ------------------------------
    def _cron_env(self, cron_xmlid):
        """Job model in the context a cron run gives it."""
        cron = self.env.ref(cron_xmlid)
        progress = self.env["ir.cron.progress"].create({"cron_id": cron.id})
        lastcall = fields.Datetime.now() - timedelta(minutes=1)
        return (
            self.Job.with_context(lastcall=lastcall, ir_cron_progress_id=progress.id),
            progress,
        )

    def test_poll_batches(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "cetmix_tower_drone.cron_batch_size", "2"
        )
        jobs = [self.running_job() for __ in range(3)]
        Job, progress = self._cron_env("cetmix_tower_drone.ir_cron_poll_drone_jobs")

        Job._cron_poll()
        polled = [call["path"] for call in self.network.find("GET")]
        self.assertEqual(polled, [f"/jobs/{job.nonce}" for job in jobs[:2]])
        self.assertEqual((progress.done, progress.remaining), (2, 1))

        self.network.reset()
        Job._cron_poll()
        polled = [call["path"] for call in self.network.find("GET")]
        self.assertEqual(polled, [f"/jobs/{jobs[2].nonce}"])
        self.assertEqual((progress.done, progress.remaining), (1, 0))
        self.assertTrue(all(job.last_check for job in jobs))

        # Round complete: nothing is due until the next lastcall
        self.network.reset()
        Job._cron_poll()
        self.assertFalse(self.network.calls)

    @mute_logger(JOB_LOGGER)
    def test_stale_pending_batches(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "cetmix_tower_drone.cron_batch_size", "1"
        )
        jobs = [self.launch().sudo() for __ in range(2)]
        self.env.cr.postcommit.clear()
        for job in jobs:
            self._age(job)
        Job, progress = self._cron_env(
            "cetmix_tower_drone.ir_cron_check_drone_job_timeout"
        )
        for job in jobs:
            self.network.reset()
            self.network.set(
                self.controller_1, get=requests.exceptions.ConnectTimeout()
            )
            Job._cron_check_timeout()
            self.assertEqual(
                [call["path"] for call in self.network.find("GET")],
                [f"/jobs/{job.nonce}"],
            )
            self.assertEqual(job.state, "pending")
        self.assertEqual((progress.done, progress.remaining), (1, 0))

    @mute_logger("odoo.addons.base.models.res_config")
    def test_cron_batch_size_setting(self):
        ICP = self.env["ir.config_parameter"].sudo()
        ICP.set_param("cetmix_tower_drone.cron_batch_size", "not a number")
        self.assertEqual(self.Job._get_cron_batch_size(), 20)
        with self.assertRaises(ValidationError):
            self.env["res.config.settings"].create(
                {"cetmix_tower_drone_cron_batch_size": 0}
            )
        self.env["res.config.settings"].create(
            {"cetmix_tower_drone_cron_batch_size": 5}
        ).execute()
        self.assertEqual(ICP.get_param("cetmix_tower_drone.cron_batch_size"), "5")
        self.assertEqual(self.Job._get_cron_batch_size(), 5)

    # ------------------------------
    # RPC surface
    # ------------------------------
    def test_public_methods(self):
        """Only intended entry points are public; sudo writers are private."""
        from ..models import base, cx_tower_drone_controller, cx_tower_drone_skill

        classes = (
            CxTowerDroneJob,
            base.Base,
            cx_tower_drone_controller.CxTowerDroneController,
            cx_tower_drone_skill.CxTowerDroneSkill,
        )
        public = {
            name
            for cls in classes
            for name, member in vars(cls).items()
            if callable(member)
            and not name.startswith("_")
            and name not in ("create", "write")
        }
        self.assertEqual(
            public,
            {
                "action_cancel",
                "action_check_health",
                "action_generate_payload_key",
                "launch_drone",
            },
        )
