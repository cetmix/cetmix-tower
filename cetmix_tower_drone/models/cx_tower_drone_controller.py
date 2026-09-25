# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import hmac
import logging
import re

import psycopg2
import requests
from cryptography.fernet import Fernet
from urllib3.exceptions import NewConnectionError

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .constants import (
    CONTROLLER_AVAILABLE,
    CONTROLLER_DRAINING,
    CONTROLLER_ERROR,
    CONTROLLER_NOT_REACHABLE,
    JOB_ACTIVE_STATES,
    OUTBOUND_TIMEOUT,
)

_logger = logging.getLogger(__name__)

# Statuses a controller may report about itself
INBOUND_STATUSES = (CONTROLLER_AVAILABLE, CONTROLLER_ERROR, CONTROLLER_NOT_REACHABLE)

# Exceptions raised before a request could reach the controller.
# SSLError and InvalidHeader are not among them: requests also raises them
# while reading the response, after the request was sent.
NOT_SENT_EXCEPTIONS = (
    requests.exceptions.ConnectTimeout,
    requests.exceptions.InvalidURL,
    requests.exceptions.MissingSchema,
    requests.exceptions.InvalidSchema,
)


class CxTowerDroneController(models.Model):
    """External process that accepts jobs and runs them on its drones."""

    _name = "cx.tower.drone.controller"
    _inherit = [
        "cx.tower.reference.mixin",
        "cx.tower.vault.mixin",
        "cx.tower.tag.mixin",
    ]
    _description = "Cetmix Tower Drone Controller"
    _order = "priority, id"

    SECRET_FIELDS = ["drone_api_key", "payload_key", "drone_response_key"]

    active = fields.Boolean(default=True)
    priority = fields.Integer(
        default=10, help="Lower value means higher priority when selecting"
    )
    skill_ids = fields.Many2many(
        comodel_name="cx.tower.drone.skill",
        relation="cx_tower_drone_controller_skill_rel",
        column1="controller_id",
        column2="skill_id",
        string="Skills",
        help="Skills reported by the last successful health check",
    )
    controller_url = fields.Char(string="URL", required=True)
    drone_api_key = fields.Char(
        string="Drone API Key",
        groups="cetmix_tower_base.group_root",
        help="Sent by Tower to the controller",
    )
    payload_key = fields.Char(
        groups="cetmix_tower_base.group_root",
        help="Fernet key used to encrypt job payloads. "
        "Generated automatically when left empty",
    )
    drone_response_key = fields.Char(
        groups="cetmix_tower_base.group_root",
        help="Sent by the controller to Tower",
    )
    status = fields.Selection(
        selection=[
            (CONTROLLER_AVAILABLE, "Available"),
            (CONTROLLER_NOT_REACHABLE, "Not Reachable"),
            (CONTROLLER_ERROR, "Error"),
            (CONTROLLER_DRAINING, "Draining"),
        ],
        default=CONTROLLER_NOT_REACHABLE,
        required=True,
    )
    max_running_jobs = fields.Integer(
        string="Max Jobs",
        default=0,
        help="Maximum number of pending and running jobs. 0 means unlimited",
    )
    running_job_count = fields.Integer(
        string="Running Jobs",
        compute="_compute_running_job_count",
        help="Pending and running jobs, as counted against Max Jobs",
    )
    job_count = fields.Integer(
        string="Jobs",
        compute="_compute_job_count",
        help="Drone jobs dispatched to this controller",
    )
    reservation_seq = fields.Integer(
        default=0,
        copy=False,
        groups="cetmix_tower_base.group_root",
        help="Serialization token for job reservation. Its value is meaningless",
    )
    last_health_check = fields.Datetime(copy=False)

    _sql_constraints = [
        (
            "controller_url_unique",
            "UNIQUE(controller_url)",
            "Controller URL must be unique",
        ),
        (
            "max_running_jobs_positive",
            "CHECK(max_running_jobs >= 0)",
            "Max Jobs cannot be negative",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """Generate a Fernet payload key when none is given."""
        for vals in vals_list:
            if vals.get("payload_key"):
                self._check_payload_key(vals["payload_key"])
            else:
                vals["payload_key"] = self._generate_payload_key()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("payload_key"):
            self._check_payload_key(vals["payload_key"])
        return super().write(vals)

    @api.model
    def _generate_payload_key(self):
        """Return a new Fernet key as a string.

        Returns:
            str: url-safe base64-encoded Fernet key.
        """
        return Fernet.generate_key().decode()

    @api.model
    def _check_payload_key(self, payload_key):
        """Raise if the payload key is not a valid Fernet key.

        Args:
            payload_key (str): Key to check.
        """
        try:
            Fernet(payload_key.encode())
        except (ValueError, TypeError) as exc:
            raise ValidationError(
                self.env._("Payload Key must be a valid Fernet key.")
            ) from exc

    def action_generate_payload_key(self):
        """Generate a Fernet payload key, store it, and show it for copying.

        Returns:
            dict: Action that opens the show-key wizard.
        """
        self.ensure_one()
        key = self._generate_payload_key()
        self.write({"payload_key": key})
        # Non-stored: create would discard the key; set it on the cache after.
        wizard = self.env["cx.tower.drone.payload.key.wizard"].create(
            {"controller_id": self.id}
        )
        wizard.payload_key = key
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Payload Key"),
            "res_model": "cx.tower.drone.payload.key.wizard",
            "res_id": wizard.id,
            "views": [(False, "form")],
            "target": "new",
        }

    def _compute_running_job_count(self):
        counts = dict(
            self.env["cx.tower.drone.job"]
            .sudo()
            ._read_group(
                [
                    ("controller_id", "in", self.ids),
                    ("state", "in", JOB_ACTIVE_STATES),
                ],
                ["controller_id"],
                ["__count"],
            )
        )
        for controller in self:
            controller.running_job_count = counts.get(controller, 0)

    def _compute_job_count(self):
        counts = dict(
            self.env["cx.tower.drone.job"]
            .sudo()
            ._read_group(
                [("controller_id", "in", self.ids)],
                ["controller_id"],
                ["__count"],
            )
        )
        for controller in self:
            controller.job_count = counts.get(controller, 0)

    def action_view_jobs(self):
        """Open drone jobs run on this controller.

        Returns:
            dict: Window action on ``cx.tower.drone.job``.
        """
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_drone.cx_tower_drone_job_action"
        )
        action["domain"] = [("controller_id", "=", self.id)]
        return action

    # ------------------------------
    # Reservation
    # ------------------------------
    def _reserve(self, job=None):
        """Reserve one job slot on this controller.

        Writes the controller row so that a concurrent reservation committed
        after this transaction's snapshot raises a serialization failure
        instead of going unnoticed under REPEATABLE READ.

        Args:
            job (cx.tower.drone.job): Job being dispatched, excluded from
                the count. Empty or None when the job does not exist yet.

        Returns:
            bool: True if the slot is reserved.
        """
        self.ensure_one()
        cr = self.env.cr
        cr.execute(
            "SELECT id FROM cx_tower_drone_controller WHERE id = %s FOR UPDATE",
            [self.id],
        )
        cr.execute(
            "UPDATE cx_tower_drone_controller "
            "SET reservation_seq = reservation_seq + 1 WHERE id = %s",
            [self.id],
        )
        self.invalidate_recordset(["reservation_seq"])
        max_running_jobs = self.sudo().max_running_jobs
        if not max_running_jobs:
            return True
        domain = [
            ("controller_id", "=", self.id),
            ("state", "in", JOB_ACTIVE_STATES),
        ]
        if job:
            domain.append(("id", "!=", job.id))
        count = self.env["cx.tower.drone.job"].sudo().search_count(domain)
        return count < max_running_jobs

    # ------------------------------
    # Outbound HTTP
    # ------------------------------
    def _drone_request(self, method, path, payload=None):
        """Send a request to the controller.

        Args:
            method (str): HTTP method.
            path (str): Path starting with '/'.
            payload (dict): JSON body, if any.

        Returns:
            requests.Response: Response. Exceptions are not caught.
        """
        self.ensure_one()
        controller = self.sudo()
        api_key = controller._get_secret_value("drone_api_key") or ""
        return requests.request(
            method,
            f"{controller.controller_url.rstrip('/')}{path}",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=(OUTBOUND_TIMEOUT, OUTBOUND_TIMEOUT),
            # A followed redirect could fail after the first request was sent
            # and be taken for "not sent"
            allow_redirects=False,
        )

    @api.model
    def _request_not_sent(self, exc):
        """Tell whether a request exception proves nothing reached the controller.

        Connection refused, DNS failures and connect timeouts happen before
        the request is sent. Anything else (TLS error, read timeout, reset
        after sending, invalid response header, ...) may have reached the
        controller.

        Args:
            exc (Exception): Exception raised while sending the request.

        Returns:
            bool: True if the request provably was not sent.
        """
        if isinstance(exc, NOT_SENT_EXCEPTIONS):
            return True
        if isinstance(exc, requests.exceptions.ConnectionError) and exc.args:
            reason = getattr(exc.args[0], "reason", None)
            return isinstance(reason, NewConnectionError)
        return False

    def _set_status(self, status):
        """Write status unless the controller is draining.

        Args:
            status (str): New status.
        """
        to_update = self.sudo().filtered(
            lambda c: c.status not in (status, CONTROLLER_DRAINING)
        )
        if to_update:
            to_update.write({"status": status})

    # ------------------------------
    # Inbound HTTP
    # ------------------------------
    def _check_response_key(self, token):
        """Compare the bearer token with the controller response key.

        Args:
            token (str): Token from the Authorization header.

        Returns:
            bool: True if it matches.
        """
        self.ensure_one()
        secret = self.sudo()._get_secret_value("drone_response_key")
        if not secret or not token:
            return False
        return hmac.compare_digest(secret.encode(), token.encode())

    @api.model
    def _http_status(self, token, data):
        """Handle the controller status route.

        Args:
            token (str): Bearer token.
            data (dict): Request JSON.

        Returns:
            int: HTTP status code.
        """
        reference = data.get("reference")
        controller = (
            self.sudo()
            .with_context(active_test=False)
            .search([("reference", "=", reference)], limit=1)
            if isinstance(reference, str) and reference
            else self.browse()
        )
        if not controller:
            return 404
        if not controller._check_response_key(token):
            return 403
        status = data.get("status")
        if status not in INBOUND_STATUSES:
            return 400
        if controller.status == CONTROLLER_DRAINING:
            return 409
        controller._set_status(status)
        return 200

    # ------------------------------
    # Health
    # ------------------------------
    @api.model
    def _cron_check_health(self):
        """Check health of active, non-draining controllers.

        Each controller runs in its own savepoint so one failure does not
        abort the rest of the cron.
        """
        controllers = self.sudo().search(
            [("status", "!=", CONTROLLER_DRAINING)], order="id"
        )
        for controller in controllers:
            try:
                with self.env.cr.savepoint():
                    controller._check_health()
            except Exception:
                _logger.exception(
                    "Drone controller %s health check failed", controller.id
                )

    def _check_health(self):
        """Call ``GET /health`` and store the skills it reports.

        A healthy controller answers 200 with a JSON object whose
        ``skills`` list holds reference tokens. Anything else updates
        the status and leaves the stored skills as they are. A lost
        race to create a new skill leaves this controller unchanged.

        Returns:
            bool: True when a valid skills list was stored.
        """
        self.ensure_one()
        try:
            response = self._drone_request("GET", "/health")
        except requests.exceptions.RequestException as exc:
            _logger.warning(
                "Drone controller %s health check failed: %s",
                self.id,
                type(exc).__name__,
            )
            self._set_status(CONTROLLER_NOT_REACHABLE)
            return False
        if response.status_code != 200:
            self._set_status(CONTROLLER_ERROR)
            return False
        tokens = self._parse_health_skills(response)
        if tokens is None:
            self._set_status(CONTROLLER_ERROR)
            return False
        try:
            with self.env.cr.savepoint():
                skills = self._sync_health_skills(tokens)
                vals = {
                    "last_health_check": fields.Datetime.now(),
                    "skill_ids": [(6, 0, skills.ids)],
                }
                if self.status != CONTROLLER_DRAINING:
                    vals["status"] = CONTROLLER_AVAILABLE
                self.sudo().write(vals)
        except psycopg2.IntegrityError:
            return False
        return True

    def _parse_health_skills(self, response):
        """Return the skill tokens from a health body.

        A token is valid when it matches ``[a-z0-9_]+``. Extra keys are
        ignored. Duplicate tokens count once. A missing body, a body
        that is not a JSON object, or a ``skills`` list that is not a
        list of valid tokens is rejected.

        Args:
            response (requests.Response): Health response.

        Returns:
            list | None: Unique tokens, or None when the body is not a
                skills report.
        """
        try:
            data = response.json()
        except ValueError:
            return None
        if not isinstance(data, dict):
            return None
        tokens = data.get("skills")
        if not isinstance(tokens, list):
            return None
        seen = []
        for token in tokens:
            if not isinstance(token, str) or not re.fullmatch(r"[a-z0-9_]+", token):
                return None
            if token not in seen:
                seen.append(token)
        return seen

    def _sync_health_skills(self, tokens):
        """Return skill records for health tokens, creating missing ones.

        An existing record keeps its name and reference. Runs with
        ``sudo()`` so the health cron and Check Connection can both
        create skills.

        Args:
            tokens (list): Valid skill references.

        Returns:
            cx.tower.drone.skill: Records for ``tokens``, in that order.

        Raises:
            psycopg2.IntegrityError: If another transaction has already
                inserted one of these references. That row is not visible
                here, and this method does not look it up again.
        """
        skill_model = self.env["cx.tower.drone.skill"].sudo()
        if not tokens:
            return skill_model.browse()
        by_reference = {
            skill.reference: skill
            for skill in skill_model.search([("reference", "in", tokens)])
        }
        skills = skill_model.browse()
        for token in tokens:
            skill = by_reference.get(token)
            if not skill:
                skill = skill_model.create({"name": token, "reference": token})
                by_reference[token] = skill
            skills |= skill
        return skills

    def action_check_health(self):
        """Check the connection from the controller form and tell the result.

        Unlike the cron, this checks inactive and draining controllers too.
        A draining controller keeps its status, as everywhere else.

        Returns:
            dict: Notification with the status after the check.
        """
        self.ensure_one()
        healthy = self._check_health()
        self.invalidate_recordset(["status", "last_health_check"])
        status = dict(self._fields["status"]._description_selection(self.env)).get(
            self.status
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success" if healthy else "warning",
                "title": self.env._("Connection checked")
                if healthy
                else self.env._("No connection"),
                "message": self.env._("Status: %(status)s", status=status),
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
