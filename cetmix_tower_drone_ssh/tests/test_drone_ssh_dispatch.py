# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import contextlib
from datetime import timedelta
from unittest.mock import patch

from psycopg2.errors import LockNotAvailable

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.cetmix_tower_drone.tests.common import JOB_LOGGER
from odoo.addons.cetmix_tower_server.models.constants import (
    COMMAND_STOPPED,
    COMMAND_TIMED_OUT,
    GENERAL_ERROR,
    SSH_CONNECTION_ERROR,
)

from ..models.constants import NO_CONTROLLER_POLICY_PARAM, NO_DRONE_CONTROLLER
from .common import TestDroneSshCommon

COMMAND_LOG_LOGGER = "odoo.addons.cetmix_tower_server.models.cx_tower_command_log"


class _Rollback(Exception):
    pass


# Post install: the queue module, when installed, is loaded too
@tagged("post_install", "-at_install")
class TestDroneSshDispatch(TestDroneSshCommon):
    # ------------------------------
    # Registration
    # ------------------------------
    def test_registration(self):
        """Skill, defer handler and zombie domain are registered."""
        self.assertIn("ssh", self.Job._get_drone_skills())
        self.assertIn("ssh", self.Job.get_drone_skills())
        with self.real_defer_handlers():
            handlers = dict(self.server_test_1._get_command_defer_handlers())
        self.assertEqual(handlers[10].__name__, "_try_defer_command_drone")
        domain = self.server_test_1._get_zombie_command_log_domain(
            fields.Datetime.now()
        )
        self.assertIn(("drone_job_id", "=", False), domain)

    # ------------------------------
    # Dispatch
    # ------------------------------
    def test_dispatch_to_controller(self):
        """The job is pending until commit, then submitted once."""
        with patch.object(
            type(self.Server), "_command_runner_ssh", autospec=True
        ) as ssh_runner:
            log = self.run_command()
            job = log.sudo().drone_job_id
            self.assertTrue(job)
            self.assertEqual(job.state, "pending")
            self.assertTrue(log.is_running)
            self.assertFalse(self.network.calls)

            self.run_postcommit()
            ssh_runner.assert_not_called()
        self.assertEqual(job.state, "running")
        self.assertEqual(len(self.network.find("POST", "/jobs")), 1)
        self.assertEqual(log.drone_controller_id, self.controller_1)
        self.assertTrue(log.is_running)

    def test_failover(self):
        """A 4xx from the first controller moves the command to the next."""
        self.network.set(self.controller_1, post=422)
        log, job = self.dispatch()
        self.assertEqual(job.state, "running")
        self.assertEqual(log.drone_controller_id, self.controller_2)

    @mute_logger(JOB_LOGGER)
    def test_all_candidates_refused(self):
        """Refused at submission: no controller, even with fallback."""
        self.ICP.set_param(NO_CONTROLLER_POLICY_PARAM, "fallback")
        self.network.set(self.controller_1, post=400)
        self.network.set(self.controller_2, post=400)
        with patch.object(
            type(self.Server), "_command_runner_ssh", autospec=True
        ) as ssh_runner:
            log, job = self.dispatch()
            ssh_runner.assert_not_called()
        self.assertEqual(job.state, "failed")
        self.assertFalse(log.is_running)
        self.assertEqual(log.command_status, NO_DRONE_CONTROLLER)

    def test_build_payload_raises(self):
        """Host key removed after the defer: local rejection, no secret."""
        command = self.Command.create(
            {
                "name": "Drone SSH secret",
                "action": "ssh_command",
                "code": f"echo #!cxtower.secret.{self.secret_2.reference}!#",
            }
        )
        log = self.run_command(command)
        self.server_test_1.write({"host_key": False})
        with self.assertLogs(JOB_LOGGER, "WARNING") as logs:
            self.run_postcommit()
        self.assertFalse(self.network.find("POST", "/jobs"))
        self.assertFalse(log.is_running)
        self.assertEqual(log.command_status, NO_DRONE_CONTROLLER)
        for line in logs.output:
            self.assertNotIn("secret top", line)
        self.assertNotIn("secret top", log.command_error or "")

    def test_missing_host_key_at_defer(self):
        """Missing host key is caught before any job is created."""
        self.server_test_1.write({"host_key": False})
        log = self.run_command()
        self.run_postcommit()
        self.assertFalse(log.is_running)
        self.assertEqual(log.command_status, SSH_CONNECTION_ERROR)
        self.assertFalse(log.sudo().drone_job_id)
        self.assertFalse(self.Job.sudo().search([]))
        self.assertFalse(self.network.calls)

    def test_no_skill_record(self):
        """Without the SSH skill record the no controller policy applies."""
        self.skill_ssh.unlink()
        log = self.run_command()
        self.assertFalse(log.is_running)
        self.assertEqual(log.command_status, NO_DRONE_CONTROLLER)

        self.ICP.set_param(NO_CONTROLLER_POLICY_PARAM, "fallback")
        log = self.run_command()
        self.assertFalse(log.is_running)
        self.assertEqual(log.command_status, 0)
        self.assertFalse(log.sudo().drone_job_id)

    def test_no_controller_policy(self):
        """Fail finishes the log; fallback runs the SSH command in Odoo."""
        (self.controller_1 | self.controller_2).write({"status": "not_reachable"})
        log = self.run_command()
        self.run_postcommit()
        self.assertFalse(log.is_running)
        self.assertEqual(log.command_status, NO_DRONE_CONTROLLER)
        self.assertFalse(log.sudo().drone_job_id)
        self.assertFalse(self.network.calls)

        self.ICP.set_param(NO_CONTROLLER_POLICY_PARAM, "fallback")
        with patch.object(
            type(self.Server),
            "_command_runner_ssh",
            autospec=True,
            side_effect=type(self.Server)._command_runner_ssh,
        ) as ssh_runner:
            log = self.run_command()
            ssh_runner.assert_called_once()
        self.assertFalse(log.is_running)
        self.assertEqual(log.command_status, 0)
        self.assertFalse(self.network.calls)

    def test_no_controller_fallback_to_queue(self):
        """Fallback hands the command to the queue when it is installed."""
        if "queue_job_id" not in self.CommandLog._fields:
            self.skipTest("cetmix_tower_server_queue is not installed")
        (self.controller_1 | self.controller_2).write({"status": "not_reachable"})
        self.ICP.set_param(NO_CONTROLLER_POLICY_PARAM, "fallback")
        with self.real_defer_handlers():
            log = self.run_command()
        self.assertTrue(log.is_running)
        self.assertTrue(log.sudo().queue_job_id)
        self.assertFalse(log.sudo().drone_job_id)

    def test_dispatched_command_not_queued(self):
        """A command taken by a drone never becomes a queue job."""
        if "queue_job_id" not in self.CommandLog._fields:
            self.skipTest("cetmix_tower_server_queue is not installed")
        with self.real_defer_handlers():
            log = self.run_command()
        self.assertTrue(log.sudo().drone_job_id)
        self.assertFalse(log.sudo().queue_job_id)

    def test_non_ssh_actions_not_dispatched(self):
        """Python, plan and file commands never reach a drone."""
        python_command = self.Command.create(
            {
                "name": "Drone Python",
                "action": "python_code",
                "code": "result = {'exit_code': 0, 'message': 'ok'}",
            }
        )
        child_plan = self.Plan.create({"name": "Drone Python Plan"})
        self.plan_line.create(
            {"sequence": 10, "plan_id": child_plan.id, "command_id": python_command.id}
        )
        plan_command = self.Command.create(
            {
                "name": "Drone Plan",
                "action": "plan",
                "flight_plan_id": child_plan.id,
            }
        )
        for command in (
            python_command,
            plan_command,
            self.command_create_file_with_template_tower_source,
        ):
            log = self.run_command(command)
            self.assertFalse(log.sudo().drone_job_id)
        self.run_postcommit()
        self.assertFalse(self.Job.sudo().search([]))
        self.assertFalse(self.network.calls)

    # ------------------------------
    # Payload
    # ------------------------------
    def test_payload(self):
        """Prepared commands and connection values, no key values."""
        server = self.Server.create(
            {
                "name": "Drone Key Server",
                "ip_v4_address": "10.0.0.1",
                "ssh_port": 2222,
                "ssh_username": "ubuntu",
                "ssh_password": "sudo-password",
                "ssh_auth_mode": "k",
                "ssh_key_id": self.key_1.id,
                "use_sudo": "p",
                "host_key": "drone-host-key",
                "os_id": self.os_debian_10.id,
            }
        )
        command = self.Command.create(
            {
                "name": "Drone SSH sudo",
                "action": "ssh_command",
                "code": f"ls && echo #!cxtower.secret.{self.secret_2.reference}!#",
            }
        )
        self.dispatch(command, server=server)
        posts = self.network.find("POST", "/jobs")
        self.assertEqual(len(posts), 1)
        envelope = self.decrypt(posts[0])
        self.assertEqual(envelope["skill"], "ssh")
        self.assertEqual(envelope["timeout"], 600)
        data = envelope["data"]
        self.assertEqual(set(data), {"commands", "sudo", "connection"})
        self.assertEqual(data["sudo"], "p")
        self.assertEqual(
            data["commands"],
            [f"{self.sudo_prefix} ls", f"{self.sudo_prefix} echo secret top"],
        )
        self.assertEqual(
            data["connection"],
            {
                "host": "10.0.0.1",
                "port": 2222,
                "username": "ubuntu",
                "auth_mode": "k",
                "password": "sudo-password",
                "ssh_key": "much key",
                "host_key": "drone-host-key",
                "skip_host_key": False,
            },
        )
        self.assertNotIn("key_values", data)

    def test_timeout_from_command_timeout(self):
        self.ICP.set_param("cetmix_tower_server.command_timeout", "0")
        __, job = self.dispatch()
        self.assertEqual(job.timeout, 0)

    def test_controller_tags(self):
        """Server tags are matched against controller tags."""
        Job = self.Job.sudo()
        self.assertEqual(
            Job._drone_skill_ssh_get_controller_tags(server=self.server_test_1),
            self.server_test_1.tag_ids,
        )
        self.assertFalse(Job._drone_skill_ssh_get_controller_tags())

        self.controller_1.write({"tag_ids": [(6, 0, self.tag_test_production.ids)]})
        # Untagged server: only the untagged controller
        __, job = self.dispatch()
        self.assertEqual(job.controller_id, self.controller_2)
        # Tagged otherwise: the tagged controller is skipped
        self.server_test_1.write({"tag_ids": [(6, 0, self.tag_test_staging.ids)]})
        __, job = self.dispatch(self.command_list_dir)
        self.assertEqual(job.controller_id, self.controller_2)
        # Matching tag
        self.server_test_1.write({"tag_ids": [(6, 0, self.tag_test_production.ids)]})
        __, job = self.dispatch(self.command_create_dir)
        self.assertEqual(job.controller_id, self.controller_1)

    # ------------------------------
    # Callback
    # ------------------------------
    def test_callback_success_advances_plan_once(self):
        self.plan_1._run_single(self.server_test_1)
        self.run_postcommit()
        plan_log = self.PlanLog.search(
            [("plan_id", "=", self.plan_1.id)], order="id desc", limit=1
        )
        first_log = plan_log.command_log_ids
        self.assertEqual(len(first_log), 1)
        job = first_log.sudo().drone_job_id
        self.assertEqual(job.state, "running")

        self.assertEqual(self.http_result(job, response="done"), 200)
        self.assertEqual(job.state, "done")
        self.assertFalse(first_log.is_running)
        self.assertEqual(first_log.command_status, 0)
        self.assertEqual(first_log.command_response, "done")
        self.assertEqual(len(plan_log.command_log_ids), 2)
        second_log = plan_log.command_log_ids - first_log
        self.assertTrue(second_log.is_running)
        self.assertTrue(second_log.sudo().drone_job_id)

        # Late delivery and a repeated callback do not advance the plan again
        self.assertEqual(self.http_result(job), 200)
        self.assertTrue(first_log._on_drone_ssh_done(job, None))
        plan_log.invalidate_recordset()
        self.assertEqual(len(plan_log.command_log_ids), 2)

    def test_callback_as_manager(self):
        """The callback runs as the manager who ran the command."""
        self.server_test_1.write({"manager_ids": [(4, self.manager.id)]})
        self.command_ssh.write({"server_ids": [(4, self.server_test_1.id)]})
        log, job = self.dispatch(
            self.command_ssh.with_user(self.manager),
            server=self.server_test_1.with_user(self.manager),
        )
        self.assertEqual(job.user_id, self.manager)
        self.assertEqual(self.http_result(job), 200)
        self.assertEqual(job.state, "done")
        self.assertFalse(job.callback_error)
        self.assertFalse(log.is_running)
        self.assertEqual(log.command_status, 0)

    @mute_logger(COMMAND_LOG_LOGGER)
    def test_callback_lock_lost(self):
        """A skipped finish() leaves the job running; a later poll ends it."""
        log, job = self.dispatch()
        original_execute = self.env.cr.execute

        def raise_lock(query, params=None, *args, **kwargs):
            query_str = query if isinstance(query, str) else str(query)
            if "FOR UPDATE NOWAIT" in query_str and "cx_tower_command_log" in (
                query_str
            ):
                raise LockNotAvailable()
            return original_execute(query, params, *args, **kwargs)

        with patch.object(self.env.cr, "execute", side_effect=raise_lock):
            self.assertEqual(self.http_result(job), 503)
        self.assertEqual(job.state, "running")
        self.assertTrue(log.is_running)

        self.network.set(
            self.controller_1,
            get=(200, {"state": "finished", "status": 0, "response": "ok"}),
        )
        job._poll()
        self.env.invalidate_all()
        self.assertEqual(job.state, "done")
        self.assertFalse(log.is_running)
        self.assertEqual(log.command_status, 0)

    def test_callback_failed_from_controller(self):
        """A controller failure without an exit code is a general error."""
        for status in (0, None):
            log, job = self.dispatch()
            self.assertEqual(
                self.http_result(job, state="failed", status=status, error="boom"),
                200,
            )
            self.assertEqual(job.state, "failed")
            self.assertEqual(log.command_status, GENERAL_ERROR)
            self.assertEqual(log.command_error, "boom")

    @mute_logger(JOB_LOGGER)
    def test_stale_pending_not_found(self):
        """A pending job unknown to the controller: no controller."""
        log = self.run_command()
        self.env.cr.postcommit.clear()
        job = log.sudo().drone_job_id
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE cx_tower_drone_job SET create_date = %s WHERE id = %s",
            [fields.Datetime.now() - timedelta(minutes=20), job.id],
        )
        self.env.invalidate_all()
        self.network.set(self.controller_1, get=404)
        self.Job._cron_check_timeout()
        self.env.invalidate_all()
        self.assertEqual(job.state, "failed")
        self.assertFalse(log.is_running)
        self.assertEqual(log.command_status, NO_DRONE_CONTROLLER)

    # ------------------------------
    # Stop and timeout
    # ------------------------------
    def test_stop_running(self):
        """Cancel is sent after commit; a late result is ignored."""
        log, job = self.dispatch()
        log.stop()
        self.assertEqual(log.command_status, COMMAND_STOPPED)
        self.assertEqual(job.state, "cancelled")
        self.assertFalse(self.network.find("POST", "/cancel"))
        self.run_postcommit()
        self.assertEqual(len(self.network.find("POST", "/cancel")), 1)

        self.assertEqual(self.http_result(job), 200)
        self.assertEqual(job.state, "cancelled")
        self.assertEqual(log.command_status, COMMAND_STOPPED)

    def test_stop_rolled_back(self):
        log, job = self.dispatch()
        with contextlib.suppress(_Rollback), self.env.cr.savepoint():
            log.stop()
            raise _Rollback()
        self.env.invalidate_all()
        self.run_postcommit()
        self.assertEqual(job.state, "running")
        self.assertTrue(log.is_running)
        self.assertFalse(self.network.find("POST", "/cancel"))

    def test_cancel_job_stops_log(self):
        """Cancelling the drone job stops its command log and flight plan."""
        self.plan_1._run_single(self.server_test_1)
        self.run_postcommit()
        plan_log = self.PlanLog.search(
            [("plan_id", "=", self.plan_1.id)], order="id desc", limit=1
        )
        log = plan_log.command_log_ids
        job = log.sudo().drone_job_id
        job.with_user(self.root).action_cancel()
        self.assertEqual(job.state, "cancelled")
        self.assertFalse(log.is_running)
        self.assertEqual(log.command_status, COMMAND_STOPPED)
        self.assertFalse(plan_log.is_running)
        self.assertEqual(len(plan_log.command_log_ids), 1)
        self.run_postcommit()
        self.assertEqual(len(self.network.find("POST", "/cancel")), 1)

    @mute_logger(COMMAND_LOG_LOGGER)
    def test_cancel_job_log_locked(self):
        """A locked log rolls the cancellation back; nothing is sent."""
        log, job = self.dispatch()
        original_execute = self.env.cr.execute

        def raise_lock(query, params=None, *args, **kwargs):
            query_str = query if isinstance(query, str) else str(query)
            if "FOR UPDATE NOWAIT" in query_str and "cx_tower_command_log" in (
                query_str
            ):
                raise LockNotAvailable()
            return original_execute(query, params, *args, **kwargs)

        with (
            patch.object(self.env.cr, "execute", side_effect=raise_lock),
            self.assertRaises(UserError),
            self.env.cr.savepoint(),
        ):
            job.with_user(self.root).action_cancel()
        self.env.invalidate_all()
        self.run_postcommit()
        self.assertEqual(job.state, "running")
        self.assertTrue(log.is_running)
        self.assertFalse(self.network.find("POST", "/cancel"))

        # Once the lock is gone the cancellation goes through
        job.with_user(self.root).action_cancel()
        self.assertEqual(job.state, "cancelled")
        self.assertEqual(log.command_status, COMMAND_STOPPED)

    def test_stop_pending(self):
        """A job stopped before its submission is never submitted."""
        log = self.run_command()
        job = log.sudo().drone_job_id
        log.stop()
        self.assertEqual(job.state, "cancelled")
        self.run_postcommit()
        self.assertFalse(self.network.find("POST", "/jobs"))
        self.assertEqual(job.state, "cancelled")
        self.assertEqual(log.command_status, COMMAND_STOPPED)

    def _silence(self, job):
        job.write({"last_heartbeat": fields.Datetime.now() - timedelta(hours=1)})
        self.env.flush_all()

    def test_drone_timeout(self):
        """Heartbeat timeout finishes the log and sends one cancel."""
        log, job = self.dispatch()
        self._silence(job)
        self.Job._cron_check_timeout()
        self.env.invalidate_all()
        self.assertEqual(job.state, "timed_out")
        self.assertFalse(log.is_running)
        self.assertEqual(log.command_status, COMMAND_TIMED_OUT)
        self.run_postcommit()
        self.assertEqual(len(self.network.find("POST", "/cancel")), 1)

    def test_zombie_cron_skips_drone_logs(self):
        log, __ = self.dispatch()
        other_log = self.CommandLog.create(
            {
                "server_id": self.server_test_1.id,
                "command_id": self.command_ssh.id,
                "start_date": fields.Datetime.now(),
            }
        )
        (log | other_log).write(
            {"start_date": fields.Datetime.now() - timedelta(hours=1)}
        )
        self.server_test_1._check_zombie_commands()
        self.env.invalidate_all()
        self.assertTrue(log.is_running)
        self.assertEqual(other_log.command_status, COMMAND_TIMED_OUT)

    def _nested_plan(self):
        child_plan = self.Plan.create({"name": "Drone child plan"})
        self.plan_line.create(
            {
                "sequence": 10,
                "plan_id": child_plan.id,
                "command_id": self.command_ssh.id,
            }
        )
        plan_command = self.Command.create(
            {
                "name": "Drone run child plan",
                "action": "plan",
                "flight_plan_id": child_plan.id,
            }
        )
        parent_plan = self.Plan.create({"name": "Drone parent plan"})
        self.plan_line.create(
            {"sequence": 10, "plan_id": parent_plan.id, "command_id": plan_command.id}
        )
        self.plan_line.create(
            {
                "sequence": 20,
                "plan_id": parent_plan.id,
                "command_id": self.command_list_dir.id,
            }
        )
        parent_plan._run_single(self.server_test_1)
        self.run_postcommit()
        parent_plan_log = self.PlanLog.search(
            [("plan_id", "=", parent_plan.id)], order="id desc", limit=1
        )
        plan_command_log = parent_plan_log.command_log_ids
        child_log = plan_command_log.triggered_plan_log_id.command_log_ids
        return parent_plan_log, plan_command_log, child_log

    def test_nested_plan_dispatched(self):
        """Nested SSH goes to a drone; the parent command waits for it."""
        parent_plan_log, plan_command_log, child_log = self._nested_plan()
        job = child_log.sudo().drone_job_id
        self.assertEqual(job.state, "running")
        self.assertTrue(plan_command_log.is_running)

        self.assertEqual(self.http_result(job), 200)
        self.assertFalse(child_log.is_running)
        self.assertFalse(plan_command_log.is_running)
        self.assertEqual(plan_command_log.command_status, 0)
        next_log = parent_plan_log.command_log_ids - plan_command_log
        self.assertEqual(next_log.command_id, self.command_list_dir)
        self.assertTrue(next_log.sudo().drone_job_id)

    def test_nested_plan_drone_timeout(self):
        """A drone timeout of the child SSH unblocks the parent command."""
        __, plan_command_log, child_log = self._nested_plan()
        self._silence(child_log.sudo().drone_job_id)
        self.Job._cron_check_timeout()
        self.env.invalidate_all()
        self.assertEqual(child_log.command_status, COMMAND_TIMED_OUT)
        self.assertFalse(plan_command_log.is_running)

    # ------------------------------
    # Result
    # ------------------------------
    def test_server_status_on_success_only(self):
        command = self.Command.create(
            {
                "name": "Drone SSH status",
                "action": "ssh_command",
                "code": "ls",
                "server_status": "stopping",
            }
        )
        original_status = self.server_test_1.status
        __, job = self.dispatch(command)
        self.http_result(job, status=1)
        self.assertEqual(self.server_test_1.status, original_status)

        __, job = self.dispatch(command)
        self.http_result(job, status=0)
        self.assertEqual(self.server_test_1.status, "stopping")

    def test_secrets_masked(self):
        """General and server-scoped secrets are masked in the log."""
        placeholder = self.Key.SECRET_VALUE_PLACEHOLDER
        key = self.Key.create(
            {
                "name": "Drone Scoped Secret",
                "key_type": "s",
                "secret_value": "general-secret-value",
            }
        )
        self.KeyValue.create(
            {
                "key_id": key.id,
                "server_id": self.server_test_1.id,
                "secret_value": "server-secret-value",
            }
        )
        command = self.Command.create(
            {
                "name": "Drone SSH scoped secret",
                "action": "ssh_command",
                "code": f"echo #!cxtower.secret.{key.reference}!#",
            }
        )
        log, job = self.dispatch(command)
        envelope = self.decrypt(self.network.find("POST", "/jobs")[0])
        self.assertIn("server-secret-value", envelope["data"]["commands"])
        self.assertNotIn("server-secret-value", log.code)

        self.http_result(
            job,
            response=["out server-secret-value"],
            error="err server-secret-value",
        )
        self.assertFalse(log.is_running)
        self.assertNotIn("server-secret-value", log.command_response)
        self.assertIn(placeholder, log.command_response)
        self.assertNotIn("server-secret-value", log.command_error)
        self.assertIn(placeholder, log.command_error)
