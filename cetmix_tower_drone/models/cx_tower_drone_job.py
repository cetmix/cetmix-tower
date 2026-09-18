# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json
import logging
import secrets
from datetime import timedelta

from cryptography.fernet import Fernet

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.osv import expression
from odoo.service.model import PG_CONCURRENCY_EXCEPTIONS_TO_RETRY

from .constants import (
    CONTROLLER_AVAILABLE,
    CONTROLLER_ERROR,
    CONTROLLER_NOT_REACHABLE,
    CRON_BATCH_SIZE_PARAM,
    DEFAULT_CRON_BATCH_SIZE,
    DELIVERY_DONE,
    DELIVERY_IGNORED,
    DELIVERY_RETRY,
    JOB_ACTIVE_STATES,
    JOB_STATE_CANCELLED,
    JOB_STATE_DONE,
    JOB_STATE_FAILED,
    JOB_STATE_PENDING,
    JOB_STATE_RUNNING,
    JOB_STATE_TIMED_OUT,
    ROUTE_JOB_HEARTBEAT,
    ROUTE_JOB_RESULT,
    STALE_PENDING_MINUTES,
    SUBMISSION_DB_RETRIES,
    SUBMIT_ACCEPTED,
    SUBMIT_AMBIGUOUS,
    SUBMIT_FENCED,
    SUBMIT_REJECTED_CONNECTION,
    SUBMIT_REJECTED_HTTP,
    SUBMIT_REJECTED_LOCAL,
    SUBMIT_UNKNOWN,
)

_logger = logging.getLogger(__name__)

# Callback fields that are set once by `launch_drone()` and never written again
CALLBACK_FIELDS = ("res_model", "res_id", "method_name", "user_id")

# Submission routine decisions after recording an outcome
_NEXT = "next"
_STOP = "stop"
_RESOLVE = "resolve"


class _CallbackNotConsumed(Exception):
    """Raised to roll back the callback savepoint on a falsy return."""


class CxTowerDroneJob(models.Model):
    """Work handed to a drone controller.

    The job is the only record of the work: it stores neither the params,
    the payload nor the result. The result is handed to the callback.
    """

    _name = "cx.tower.drone.job"
    _description = "Cetmix Tower Drone Job"
    _order = "id desc"

    skill_id = fields.Many2one(
        comodel_name="cx.tower.drone.skill",
        required=True,
        ondelete="restrict",
    )
    controller_id = fields.Many2one(
        comodel_name="cx.tower.drone.controller",
        required=True,
        ondelete="restrict",
        index=True,
        help="Controller that accepted the job",
    )
    nonce = fields.Char(
        required=True,
        index=True,
        copy=False,
        groups="cetmix_tower_base.group_root",
    )
    state = fields.Selection(
        selection=[
            (JOB_STATE_PENDING, "Pending"),
            (JOB_STATE_RUNNING, "Running"),
            (JOB_STATE_DONE, "Done"),
            (JOB_STATE_FAILED, "Failed"),
            (JOB_STATE_TIMED_OUT, "Timed Out"),
            (JOB_STATE_CANCELLED, "Cancelled"),
        ],
        default=JOB_STATE_PENDING,
        required=True,
    )
    res_model = fields.Char(string="Target Model", required=True)
    res_id = fields.Integer(string="Target Record", required=True)
    method_name = fields.Char(string="Method", required=True)
    user_id = fields.Many2one(
        comodel_name="res.users",
        required=True,
        help="Callback is run as this user",
    )
    timeout = fields.Integer(help="Seconds without heartbeat. 0 means no timeout")
    last_heartbeat = fields.Datetime()
    last_check = fields.Datetime(
        copy=False,
        help="Last time a cron asked the controller about this job",
    )
    date_done = fields.Datetime(string="Done Date")
    callback_error = fields.Text()
    callback_attempts = fields.Integer()

    _sql_constraints = [
        ("nonce_unique", "UNIQUE(nonce)", "Nonce must be unique"),
    ]

    @api.depends("skill_id", "nonce")
    def _compute_display_name(self):
        for job in self.sudo():
            job.display_name = f"{job.skill_id.name} {(job.nonce or '')[:8]}"

    def write(self, vals):
        """Callback fields are set once in `launch_drone()` and never written."""
        protected = [field for field in CALLBACK_FIELDS if field in vals]
        if protected:
            raise AccessError(
                self.env._(
                    "Not allowed to change field(s): %(fields)s",
                    fields=", ".join(protected),
                )
            )
        return super().write(vals)

    # ------------------------------
    # Skill registry
    # ------------------------------
    def _get_drone_skills(self):
        """Inheriting modules MUST call super() and add their skills.

        Returns:
            dict: {code: {
                "build_payload": callable(controller, **params) -> dict
                    (JSON-serializable),
                "get_timeout": callable(**params) -> int seconds
                    (0 = no timeout),
                "get_controller_tags": callable(**params) -> cx.tower.tag
                    recordset (optional; empty or absent = only
                    controllers without tags match),
            }}
        """
        return {}

    # ------------------------------
    # Dispatch
    # ------------------------------
    @api.model
    def _launch(self, skill_code, on_complete, params):
        """Validate, reserve a controller and create a pending job.

        Args:
            skill_code (str): Skill code.
            on_complete (method): Bound method of a single record.
            params (dict): Skill parameters, never stored.

        Returns:
            cx.tower.drone.job: Pending job (sudo) or an empty recordset.
        """
        skills = self._get_drone_skills()
        if skill_code not in skills:
            raise ValidationError(
                self.env._(
                    "Unknown drone skill '%(skill)s'. Available skills: %(skills)s",
                    skill=skill_code,
                    skills=", ".join(sorted(skills)) or self.env._("none"),
                )
            )
        target = getattr(on_complete, "__self__", None)
        method_name = getattr(on_complete, "__name__", None)
        if target is None or not method_name:
            raise ValidationError(
                self.env._(
                    "The completion callback must be a bound method of a record."
                )
            )
        if not isinstance(target, models.BaseModel) or len(target) != 1:
            raise ValidationError(
                self.env._(
                    "The completion callback must be bound to exactly one record."
                )
            )

        skill_def = skills[skill_code]
        skill = (
            self.env["cx.tower.drone.skill"]
            .sudo()
            .search([("code", "=", skill_code)], limit=1)
        )
        if not skill:
            return self.browse()
        controller = next(
            (
                candidate
                for candidate in self._select_candidates(skill, skill_def, params)
                if candidate._reserve()
            ),
            None,
        )
        if not controller:
            return self.browse()

        job = self.sudo().create(
            {
                "skill_id": skill.id,
                "controller_id": controller.id,
                "nonce": secrets.token_urlsafe(32),
                "timeout": int(skill_def["get_timeout"](**params) or 0),
                "res_model": target._name,
                "res_id": target.id,
                "method_name": method_name,
                "user_id": self.env.uid,
            }
        )
        job._register_submission(params)
        return job

    @api.model
    def _select_candidates(self, skill, skill_def, params, exclude=None):
        """Return controllers that may take a job of this skill.

        Capacity is not checked here: it is reserved by
        ``cx.tower.drone.controller._reserve()``.

        Args:
            skill (cx.tower.drone.skill): Skill.
            skill_def (dict): Skill definition from ``_get_drone_skills()``.
            params (dict): Skill parameters.
            exclude (cx.tower.drone.controller): Controllers to skip.

        Returns:
            cx.tower.drone.controller: Candidates by priority, id.
        """
        get_tags = skill_def.get("get_controller_tags")
        tags = get_tags(**params) if get_tags else None
        tag_ids = set(tags.ids) if tags else set()
        domain = [
            ("status", "=", CONTROLLER_AVAILABLE),
            ("skill_ids", "in", skill.ids),
        ]
        if exclude:
            domain.append(("id", "not in", exclude.ids))
        controllers = (
            self.env["cx.tower.drone.controller"]
            .sudo()
            .search(domain, order="priority, id")
        )
        return controllers.filtered(
            lambda c: not c.tag_ids or tag_ids.intersection(c.tag_ids.ids)
        )

    def _register_submission(self, params):
        """Submit the job after the current transaction commits.

        Args:
            params (dict): Skill parameters, held in memory only.
        """
        self.ensure_one()
        job_id = self.id
        env = self.env
        registry = env.registry

        def submit():
            try:
                with registry.cursor() as cr:
                    env(cr=cr)["cx.tower.drone.job"].sudo().browse(job_id)._submit(
                        params
                    )
            except Exception:
                _logger.exception("Drone job %s: submission failed", job_id)

        env.cr.postcommit.add(submit)

    def _submit(self, params):
        """Submit the job to its controller, failing over when rejected.

        Runs after the caller's commit in its own cursor and commits each
        step. Never re-sends a POST after a failed write, and never moves to
        another controller while acceptance is unknown.

        Args:
            params (dict): Skill parameters as passed to `launch_drone()`.
        """
        self.ensure_one()
        cr = self.env.cr
        params = {
            key: value.with_env(value.env(cr=cr))
            if isinstance(value, models.BaseModel)
            else value
            for key, value in params.items()
        }
        skill = self.skill_id
        skill_def = self._get_drone_skills().get(skill.code, {})
        tried = self.env["cx.tower.drone.controller"]
        controller = self.controller_id
        while controller:
            tried |= controller
            claim = self._submit_claim(controller)
            if claim == _STOP:
                return
            if claim == _NEXT:
                decision = _NEXT
            else:
                outcome = self._submit_send(controller, skill_def, params)
                decision = self._submit_record(controller, outcome)
                if decision == _RESOLVE:
                    outcome = self._submit_resolve(controller)
                    decision = self._submit_record(controller, outcome)
            if decision == _STOP:
                return
            controller = self._select_candidates(
                skill, skill_def, params, exclude=tried
            )[:1]

        self._deliver(
            JOB_STATE_FAILED,
            {
                "status": None,
                "response": None,
                "error": self.env._("No drone controller accepted the job"),
            },
            from_controller=False,
        )
        cr.commit()  # pylint: disable=invalid-commit

    def _submit_claim(self, controller):
        """Reserve the controller and commit it as the job controller.

        Args:
            controller (cx.tower.drone.controller): Candidate.

        Returns:
            str: `_STOP` when the job is no longer pending or the claim could
                not be written, `_NEXT` when the controller is full, None
                when claimed.
        """
        cr = self.env.cr
        for __ in range(SUBMISSION_DB_RETRIES):
            try:
                cr.execute(
                    "SELECT state FROM cx_tower_drone_job WHERE id = %s FOR UPDATE",
                    [self.id],
                )
                row = cr.fetchone()
                if not row or row[0] != JOB_STATE_PENDING:
                    # Decided meanwhile: nothing was written, end the transaction
                    cr.commit()  # pylint: disable=invalid-commit
                    return _STOP
                if not controller._reserve(job=self):
                    cr.rollback()
                    return _NEXT
                self.write({"controller_id": controller.id})
                cr.commit()  # pylint: disable=invalid-commit
                return None
            except PG_CONCURRENCY_EXCEPTIONS_TO_RETRY:
                cr.rollback()
        _logger.warning(
            "Drone job %s: could not claim controller %s, left pending",
            self.id,
            controller.id,
        )
        return _STOP

    def _submit_send(self, controller, skill_def, params):
        """Build, encrypt and POST the payload to the controller.

        Args:
            controller (cx.tower.drone.controller): Claimed controller.
            skill_def (dict): Skill definition.
            params (dict): Skill parameters.

        Returns:
            str: Submission outcome.
        """
        try:
            payload_key = controller._get_secret_value("payload_key")
            callback_url, heartbeat_url = self._get_callback_urls()
            envelope = {
                "nonce": self.nonce,
                "callback_url": callback_url,
                "heartbeat_url": heartbeat_url,
                "timeout": self.timeout,
                "skill": self.skill_id.code,
                "data": skill_def["build_payload"](controller, **params),
            }
            token = (
                Fernet(payload_key.encode())
                .encrypt(json.dumps(envelope).encode())
                .decode()
            )
        except Exception as exc:
            self.env.cr.rollback()
            _logger.warning(
                "Drone job %s: payload for controller %s could not be built: %s",
                self.id,
                controller.id,
                type(exc).__name__,
            )
            return SUBMIT_REJECTED_LOCAL
        try:
            response = controller._drone_request("POST", "/jobs", {"payload": token})
        except Exception as exc:
            _logger.warning(
                "Drone job %s: submission to controller %s failed: %s",
                self.id,
                controller.id,
                type(exc).__name__,
            )
            if controller._request_not_sent(exc):
                return SUBMIT_REJECTED_CONNECTION
            return SUBMIT_AMBIGUOUS
        if 200 <= response.status_code < 300:
            return SUBMIT_ACCEPTED
        if 400 <= response.status_code < 500:
            return SUBMIT_REJECTED_HTTP
        return SUBMIT_AMBIGUOUS

    def _submit_resolve(self, controller):
        """Find out whether an ambiguous submission was accepted.

        Args:
            controller (cx.tower.drone.controller): Controller that got the
                ambiguous submission.

        Returns:
            str: `SUBMIT_ACCEPTED`, `SUBMIT_FENCED` or `SUBMIT_UNKNOWN`.
        """
        try:
            response = controller._drone_request("GET", f"/jobs/{self.nonce}")
        except Exception:
            return SUBMIT_UNKNOWN
        if 200 <= response.status_code < 300:
            return SUBMIT_ACCEPTED
        if response.status_code != 404:
            return SUBMIT_UNKNOWN
        # Not accepted as far as the controller knows now: fence the nonce so
        # that a late POST cannot start work before failing over.
        try:
            response = controller._drone_request("POST", f"/jobs/{self.nonce}/fence")
            answer = response.json()
        except Exception:
            return SUBMIT_UNKNOWN
        answer = answer.get("state") if isinstance(answer, dict) else None
        if answer == "fenced":
            return SUBMIT_FENCED
        if answer == "accepted":
            return SUBMIT_ACCEPTED
        return SUBMIT_UNKNOWN

    def _submit_record(self, controller, outcome):
        """Record a submission outcome unless the job was decided meanwhile.

        Only the database write is retried; nothing is sent again.

        Args:
            controller (cx.tower.drone.controller): Controller of the attempt.
            outcome (str): Submission outcome.

        Returns:
            str: `_STOP`, `_NEXT` or `_RESOLVE`.
        """
        cr = self.env.cr
        for __ in range(SUBMISSION_DB_RETRIES):
            try:
                cr.execute(
                    "SELECT state FROM cx_tower_drone_job "
                    "WHERE id = %s FOR UPDATE NOWAIT",
                    [self.id],
                )
                row = cr.fetchone()
                state = row[0] if row else None
                if state != JOB_STATE_PENDING:
                    # Decided meanwhile: nothing was written, end the transaction
                    cr.commit()  # pylint: disable=invalid-commit
                    if state == JOB_STATE_CANCELLED and outcome in (
                        SUBMIT_ACCEPTED,
                        SUBMIT_AMBIGUOUS,
                        SUBMIT_UNKNOWN,
                    ):
                        self._send_cancel()
                    return _STOP
                if outcome == SUBMIT_AMBIGUOUS:
                    cr.commit()  # pylint: disable=invalid-commit
                    return _RESOLVE
                decision = _NEXT
                if outcome in (SUBMIT_ACCEPTED, SUBMIT_UNKNOWN):
                    self.write(
                        {
                            "state": JOB_STATE_RUNNING,
                            "last_heartbeat": fields.Datetime.now(),
                        }
                    )
                    decision = _STOP
                if outcome == SUBMIT_REJECTED_CONNECTION:
                    controller._set_status(CONTROLLER_NOT_REACHABLE)
                elif outcome in (SUBMIT_REJECTED_HTTP, SUBMIT_FENCED, SUBMIT_UNKNOWN):
                    controller._set_status(CONTROLLER_ERROR)
                cr.commit()  # pylint: disable=invalid-commit
                return decision
            except PG_CONCURRENCY_EXCEPTIONS_TO_RETRY:
                cr.rollback()
        _logger.warning(
            "Drone job %s: could not record submission outcome, left pending",
            self.id,
        )
        return _STOP

    def _get_callback_urls(self):
        """Return the result and heartbeat URLs sent to the controller.

        Returns:
            tuple: (callback_url, heartbeat_url)
        """
        base_url = (
            self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        ).rstrip("/")
        return f"{base_url}{ROUTE_JOB_RESULT}", f"{base_url}{ROUTE_JOB_HEARTBEAT}"

    # ------------------------------
    # Delivery
    # ------------------------------
    def _deliver(
        self, state, result, from_controller=True, expect_heartbeat_before=None
    ):
        """Move the job to a terminal state and call its callback.

        Args:
            state (str): `done`, `failed` or `timed_out`.
            result (dict): `status`, `response`, `error`; None for timeout.
            from_controller (bool): The delivery came from the controller,
                so it refreshes `last_heartbeat`.
            expect_heartbeat_before (datetime): Timeout cron only. The
                delivery is ignored if `last_heartbeat` differs from it.

        Returns:
            str: `done`, `retry` or `ignored`.
        """
        self.ensure_one()
        job = self.sudo()
        cr = self.env.cr
        try:
            with cr.savepoint():
                cr.execute(
                    "SELECT state, last_heartbeat FROM cx_tower_drone_job "
                    "WHERE id = %s FOR UPDATE NOWAIT",
                    [job.id],
                )
                row = cr.fetchone()
        except PG_CONCURRENCY_EXCEPTIONS_TO_RETRY:
            return DELIVERY_RETRY
        if not row:
            return DELIVERY_IGNORED
        current_state, last_heartbeat = row
        job.invalidate_recordset()
        if expect_heartbeat_before is not None and (
            current_state != JOB_STATE_RUNNING
            or last_heartbeat != expect_heartbeat_before
        ):
            return DELIVERY_IGNORED

        now = fields.Datetime.now()
        if from_controller:
            job.write({"last_heartbeat": now})
        if current_state not in JOB_ACTIVE_STATES:
            return DELIVERY_IGNORED

        location = f"{job.res_model}.{job.method_name}"
        target = job._get_callback_target()
        if not target:
            job.write(
                {
                    "state": JOB_STATE_FAILED,
                    "callback_error": self.env._(
                        "Callback %(location)s could not be resolved",
                        location=location,
                    ),
                    "date_done": now,
                }
            )
            return DELIVERY_IGNORED

        attempts = job.callback_attempts + 1
        job.write({"callback_attempts": attempts})
        try:
            with cr.savepoint():
                job.write({"state": state})
                consumed = getattr(target, job.method_name)(
                    job.with_user(job.user_id), result
                )
                if not consumed:
                    raise _CallbackNotConsumed()
                job.write({"date_done": now})
        except _CallbackNotConsumed:
            return DELIVERY_RETRY
        except Exception as exc:
            _logger.exception("Drone job %s: callback %s failed", job.id, location)
            job.write(
                {
                    "callback_error": self.env._(
                        "%(error)s in %(location)s, attempt %(attempt)s",
                        error=type(exc).__name__,
                        location=location,
                        attempt=attempts,
                    )
                }
            )
            return DELIVERY_RETRY
        return DELIVERY_DONE

    def _get_callback_target(self):
        """Resolve the callback target record.

        Returns:
            recordset: Target record as the job user, or None if the model,
                the record or the method no longer exists.
        """
        self.ensure_one()
        if self.res_model not in self.env:
            return None
        model = self.env[self.res_model]
        if self.method_name in model._fields or not callable(
            getattr(type(model), self.method_name, None)
        ):
            return None
        target = model.sudo().browse(self.res_id).exists()
        if not target:
            return None
        return target.with_user(self.user_id)

    # ------------------------------
    # Cancel
    # ------------------------------
    def action_cancel(self):
        """Cancel jobs from the UI. Tower Root only."""
        if not self.env.user.has_group("cetmix_tower_base.group_root"):
            raise AccessError(self.env._("Only Tower Root can cancel drone jobs."))
        return self._cancel()

    def _cancel(self):
        """Cancel pending and running jobs without calling the callback.

        Performs no access check: the caller must have authorized the
        cancellation against the record the job belongs to. The controller
        is notified after the transaction commits.
        """
        jobs = self.sudo().filtered(lambda j: j.state in JOB_ACTIVE_STATES)
        if jobs:
            jobs.write(
                {"state": JOB_STATE_CANCELLED, "date_done": fields.Datetime.now()}
            )
            jobs._register_deferred_cancel(JOB_STATE_CANCELLED)
        return True

    def _register_deferred_cancel(self, expected_state):
        """Send the controller cancel after commit, if the state still holds.

        Args:
            expected_state (str): `cancelled` or `timed_out`.
        """
        job_ids = self.ids
        env = self.env
        registry = env.registry

        def send_cancel():
            try:
                with registry.cursor() as cr:
                    jobs = (
                        env(cr=cr)["cx.tower.drone.job"].sudo().browse(job_ids).exists()
                    )
                    for job in jobs.filtered(lambda j: j.state == expected_state):
                        job._send_cancel()
            except Exception:
                _logger.exception("Drone jobs %s: cancel failed", job_ids)

        env.cr.postcommit.add(send_cancel)

    def _send_cancel(self):
        """POST the cancel to the controller. Best effort, never raises."""
        self.ensure_one()
        try:
            response = self.controller_id._drone_request(
                "POST", f"/jobs/{self.nonce}/cancel"
            )
        except Exception as exc:
            _logger.warning(
                "Drone job %s: cancel failed: %s", self.id, type(exc).__name__
            )
            return
        if not 200 <= response.status_code < 300:
            _logger.warning(
                "Drone job %s: cancel answered HTTP %s", self.id, response.status_code
            )

    # ------------------------------
    # Crons
    # ------------------------------
    @api.model
    def _get_cron_batch_size(self):
        """Return how many jobs one cron batch asks controllers about.

        Returns:
            int: Batch size from the settings, or the default when unset
                or invalid.
        """
        value = self.env["ir.config_parameter"].sudo().get_param(CRON_BATCH_SIZE_PARAM)
        try:
            size = int(value)
        except (TypeError, ValueError):
            return DEFAULT_CRON_BATCH_SIZE
        return size if size > 0 else DEFAULT_CRON_BATCH_SIZE

    @api.model
    def _cron_run_batch(self, domain, method_name):
        """Ask controllers about one batch of jobs and report progress.

        A job is due once per cron round: when it was not checked since the
        last fully completed run (`lastcall`). Jobs checked by an earlier
        batch of the same round are skipped, so every due job is reached
        and the round ends. Without `lastcall` one batch is run and nothing
        is reported as remaining.

        Args:
            domain (list): Jobs that need checking.
            method_name (str): Job method that asks the controller.
        """
        lastcall = self.env.context.get("lastcall")
        if lastcall:
            domain = expression.AND(
                [
                    domain,
                    ["|", ("last_check", "=", False), ("last_check", "<=", lastcall)],
                ]
            )
        jobs = self.sudo().search(
            domain,
            order="last_check ASC NULLS FIRST, id",
            limit=self._get_cron_batch_size(),
        )
        for job in jobs:
            job.write({"last_check": fields.Datetime.now()})
            getattr(job, method_name)()
        remaining = self.sudo().search_count(domain) if lastcall else 0
        self.env["ir.cron"]._notify_progress(done=len(jobs), remaining=remaining)

    @api.model
    def _cron_check_timeout(self):
        """Reconcile stale pending jobs and time out silent running jobs."""
        jobs = self.sudo()
        now = fields.Datetime.now()
        self._cron_run_batch(
            [
                ("state", "=", JOB_STATE_PENDING),
                ("create_date", "<", now - timedelta(minutes=STALE_PENDING_MINUTES)),
            ],
            "_reconcile_pending",
        )

        jobs.flush_model(["state", "timeout", "last_heartbeat"])
        self.env.cr.execute(
            """
            SELECT id, last_heartbeat FROM cx_tower_drone_job
             WHERE state = %s
               AND timeout > 0
               AND last_heartbeat < %s - make_interval(secs => timeout)
             ORDER BY id
            """,
            [JOB_STATE_RUNNING, now],
        )
        for job_id, last_heartbeat in self.env.cr.fetchall():
            job = jobs.browse(job_id)
            result = job._deliver(
                JOB_STATE_TIMED_OUT,
                None,
                from_controller=False,
                expect_heartbeat_before=last_heartbeat,
            )
            if result == DELIVERY_DONE:
                job._register_deferred_cancel(JOB_STATE_TIMED_OUT)
            elif result == DELIVERY_RETRY:
                _logger.warning(
                    "Drone job %s: timeout delivery will be retried: %s",
                    job.id,
                    job.callback_error or "",
                )

    def _reconcile_pending(self):
        """Ask the controller about a job stuck in pending."""
        self.ensure_one()
        try:
            response = self.controller_id._drone_request("GET", f"/jobs/{self.nonce}")
        except Exception as exc:
            _logger.warning(
                "Drone job %s: pending job could not be checked: %s",
                self.id,
                type(exc).__name__,
            )
            return
        if 200 <= response.status_code < 300:
            self._adopt()
        elif response.status_code == 404:
            self._deliver(
                JOB_STATE_FAILED,
                {
                    "status": None,
                    "response": None,
                    "error": self.env._("Job was not submitted to any controller"),
                },
                from_controller=False,
            )
        else:
            _logger.warning(
                "Drone job %s: pending job check answered HTTP %s",
                self.id,
                response.status_code,
            )

    def _adopt(self):
        """Mark a pending job as running: a drone holds it."""
        self.sudo().write(
            {"state": JOB_STATE_RUNNING, "last_heartbeat": fields.Datetime.now()}
        )

    @api.model
    def _cron_poll(self):
        """Ask controllers about running jobs."""
        self._cron_run_batch([("state", "=", JOB_STATE_RUNNING)], "_poll")

    def _poll(self):
        """Ask the controller about this job and deliver a finished result."""
        self.ensure_one()
        try:
            response = self.controller_id._drone_request("GET", f"/jobs/{self.nonce}")
        except Exception:
            return
        if response.status_code == 404:
            self._deliver(
                JOB_STATE_FAILED,
                {
                    "status": None,
                    "response": None,
                    "error": self.env._("Job not found on the controller"),
                },
            )
            return
        if not 200 <= response.status_code < 300:
            return
        try:
            data = response.json()
        except ValueError:
            return
        if not isinstance(data, dict):
            return
        state = data.get("state")
        if state == "running":
            self.write({"last_heartbeat": fields.Datetime.now()})
        elif state == "finished":
            self._deliver(
                JOB_STATE_DONE,
                {
                    "status": data.get("status"),
                    "response": data.get("response"),
                    "error": data.get("error"),
                },
            )
        elif state == "failed":
            self._deliver(
                JOB_STATE_FAILED,
                {"status": None, "response": None, "error": data.get("error")},
            )

    # ------------------------------
    # Inbound HTTP
    # ------------------------------
    @api.model
    def _http_get_job(self, token, data):
        """Find the job named in an inbound request and check the key.

        Args:
            token (str): Bearer token.
            data (dict): Request JSON.

        Returns:
            tuple: (job, http_status) where http_status is None on success.
        """
        nonce = data.get("nonce")
        job = self.browse()
        if isinstance(nonce, str) and nonce:
            job = self.sudo().search([("nonce", "=", nonce)], limit=1)
        if not job:
            return job, 404
        if not job.controller_id._check_response_key(token):
            return job, 403
        return job, None

    @api.model
    def _http_result(self, token, data):
        """Handle the result route.

        Returns:
            int: HTTP status code.
        """
        job, error_status = self._http_get_job(token, data)
        if error_status:
            return error_status
        state = data.get("state")
        if state not in ("finished", "failed"):
            return 400
        result = job._deliver(
            JOB_STATE_DONE if state == "finished" else JOB_STATE_FAILED,
            {
                "status": data.get("status"),
                "response": data.get("response"),
                "error": data.get("error"),
            },
        )
        return 503 if result == DELIVERY_RETRY else 200

    @api.model
    def _http_heartbeat(self, token, data):
        """Handle the heartbeat route.

        Returns:
            int: HTTP status code.
        """
        job, error_status = self._http_get_job(token, data)
        if error_status:
            return error_status
        if job.state == JOB_STATE_RUNNING:
            job.write({"last_heartbeat": fields.Datetime.now()})
            return 200
        if job.state == JOB_STATE_PENDING:
            job._adopt()
            return 200
        return 409
