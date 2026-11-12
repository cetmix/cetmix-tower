# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import logging
import secrets

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.cetmix_tower_server.models.tools import generate_random_id

from .constants import BACKUP_CREATE_FAILED

_logger = logging.getLogger(__name__)


class CxTowerBackup(models.Model):
    """Keep backup metadata independently of the source Jet."""

    _name = "cx.tower.backup"
    _description = "Cetmix Tower Backup"
    _inherit = ["cx.tower.reference.mixin", "cx.tower.metadata.mixin"]
    _order = "create_date desc"

    name = fields.Char(required=True)
    backup_template_id = fields.Many2one(
        "cx.tower.backup.template", required=True, ondelete="restrict", readonly=True
    )
    jet_template_id = fields.Many2one(related="backup_template_id.jet_template_id")
    jet_id = fields.Many2one(
        "cx.tower.jet", ondelete="set null", index=True, readonly=True
    )
    server_id = fields.Many2one("cx.tower.server", ondelete="set null", readonly=True)
    environment_id = fields.Many2one(
        "cx.tower.environment", ondelete="set null", readonly=True
    )
    state = fields.Selection(
        [
            ("running", "Running"),
            ("done", "Done"),
            ("failed", "Failed"),
            ("deleting", "Deleting"),
            ("delete_failed", "Deletion Failed"),
        ],
        default="running",
        required=True,
        readonly=True,
    )
    variable_values = fields.Json(readonly=True)
    custom_variable_values = fields.Json(readonly=True)
    waypoint_ids = fields.One2many("cx.tower.jet.waypoint", "backup_id", readonly=True)
    plan_log_ids = fields.One2many("cx.tower.plan.log", "backup_id", readonly=True)
    created_from_command_log_id = fields.Many2one(
        "cx.tower.command.log", ondelete="set null", copy=False
    )
    delete_warning = fields.Char(compute="_compute_delete_warning")
    operation_token = fields.Char(readonly=True, copy=False)

    @api.depends("backup_template_id.plan_delete_id", "jet_id", "server_id")
    def _compute_delete_warning(self):
        """Warn when removing a record cannot remove its stored backup data.

        Returns:
            None: Assigns the warning on each backup.
        """
        for backup in self:
            backup.delete_warning = (
                self.env._(
                    "No Jet or server is left to run the Delete flight plan. "
                    "Deleting this backup removes only the record; stored data stays."
                )
                if backup.backup_template_id.plan_delete_id
                and not (backup.jet_id or backup.server_id)
                else False
            )

    @api.model_create_multi
    def create(self, vals_list):
        """Generate opaque references for runtime backups.

        Args:
            vals_list (list[dict]): Backup field values.

        Returns:
            cx.tower.backup: Created backups.
        """
        for vals in vals_list:
            if not vals.get("reference"):
                vals["reference"] = generate_random_id(
                    sections=4, population=4, separator="_"
                )
        return super().create(vals_list)

    def _get_custom_variable_values(self, extra=None):
        """Compose replayed values, metadata and protected identifiers.

        Args:
            extra (dict | None): Restore-time overrides of stored custom values.

        Returns:
            dict: Values supplied to the operation's plan.
        """
        self.ensure_one()
        return {
            **(self.custom_variable_values or {}),
            **(extra or {}),
            **{
                f"__backup_{key}": value for key, value in (self.metadata or {}).items()
            },
            "__backup": self.reference,
            "__backup_template": self.backup_template_id.reference,
        }

    @api.private
    def restore(
        self, server, name=None, state=None, variable_values=None, environment=None
    ):
        """Create a new Jet and restore this successful backup from Python only.

        Args:
            server (cx.tower.server): Destination server.
            name (str | None): Requested Jet name; empty generates a name.
            state (cx.tower.jet.state | None): Requested state after restore.
            variable_values (dict | None): Custom plan-value overrides.
            environment (cx.tower.environment | None): Destination environment.

        Returns:
            cx.tower.jet: Newly created Jet.

        Raises:
            ValidationError: Backup is not complete or Jet creation is refused.
        """
        self.ensure_one()
        self.check_access("read")
        if self.state != "done":
            raise ValidationError(
                self.env._("Only a successful backup can be restored.")
            )
        template = self.backup_template_id.jet_template_id
        chosen_environment = (
            environment or self.environment_id or template.environment_default_id
        )
        env_kwargs = (
            {"environment_id": chosen_environment.id} if chosen_environment else {}
        )
        jet = template.create_jet(
            server, name=name, variable_values=self.variable_values or {}, **env_kwargs
        )
        if not jet:
            raise ValidationError(
                self.env._("The Jet Template refused creation of the restored Jet.")
            )
        self._prepare_restored_jet(jet)
        jet.run_flight_plan(
            self.backup_template_id.plan_restore_id,
            plan_log={"backup_id": self.id, "backup_operation": "restore"},
            variable_values={
                **self._get_custom_variable_values(extra=variable_values),
                "__requested_jet_state__": state.reference if state else None,
            },
        )
        return jet

    def _prepare_restored_jet(self, jet):
        """Restore bridge data before the first Restore plan line executes.

        Args:
            jet (cx.tower.jet): New Jet to populate.
        """

    def action_delete(self):
        """Request deletion and return to the backup list.

        Returns:
            dict: Backup window action.
        """
        self.ensure_one()
        self.unlink()
        return self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_backup.cx_tower_backup_action"
        )

    def _has_running_restore(self):
        """Return whether a Restore plan still needs this backup's data.

        Returns:
            bool: True while at least one Restore plan is running.
        """
        self.ensure_one()
        return bool(
            self.env["cx.tower.plan.log"]
            .sudo()
            .with_context(active_test=False)
            .search_count(
                [
                    ("backup_id", "=", self.id),
                    ("backup_operation", "=", "restore"),
                    ("is_running", "=", True),
                ]
            )
        )

    def _check_delete(self):
        """Refuse removal while an operation still depends on the backup.

        Raises:
            ValidationError: Backup creation, deletion or restoration is running.
        """
        for backup in self:
            if backup.state in ("running", "deleting") or backup._has_running_restore():
                raise ValidationError(
                    self.env._(
                        "A backup with an operation in progress cannot be deleted."
                    )
                )

    def _delete_plan_is_busy(self):
        """Match Tower's parallel-run guard before changing deletion state.

        Returns:
            bool: Whether the configured Delete plan cannot start now.
        """
        self.ensure_one()
        plan = self.backup_template_id.plan_delete_id
        server = self.jet_id.server_id or self.server_id
        if not plan or not server or plan.allow_parallel_run:
            return False
        domain = [
            ("server_id", "=", server.id),
            ("plan_id", "=", plan.id),
            ("is_running", "=", True),
        ]
        if self.jet_id:
            domain.extend(
                [
                    ("jet_id", "=", self.jet_id.id),
                    ("jet_template_id", "=", self.jet_id.jet_template_id.id),
                ]
            )
        return bool(self.env["cx.tower.plan.log"].sudo().search_count(domain))

    # The actual super unlink is deferred to _unlink_finished after plan success.
    def unlink(self):  # pylint: disable=method-required-super
        """Delete stored data through the configured plan before its record.

        Returns:
            bool: True after handling the request. A busy Delete plan leaves
                the backup unchanged for a later attempt.

        Raises:
            ValidationError: An operation is running or a waypoint owns the backup.
        """
        self.check_access("unlink")
        self._check_delete()
        if self.waypoint_ids:
            raise ValidationError(
                self.env._("Delete the waypoint instead of its linked backup.")
            )
        for backup in self:
            backup._start_delete()
        return True

    def _delete_for_waypoint(self, waypoint):
        """Delete the backup as part of its owning waypoint's lifecycle.

        Args:
            waypoint (cx.tower.jet.waypoint): Waypoint requesting deletion.

        Raises:
            ValidationError: A backup operation is still running.
        """
        self.ensure_one()
        self._check_delete()
        self._start_delete(waypoint=waypoint)

    def _unlink_finished(self):
        """Remove the record after deletion has finished.

        Returns:
            bool: ORM unlink result.
        """
        return super().unlink()

    def _start_delete(self, waypoint=None):
        """Run the Delete plan, or remove a record with no execution host.

        Args:
            waypoint (cx.tower.jet.waypoint | None): Owner receiving callbacks.
        """
        self.ensure_one()
        plan = self.backup_template_id.plan_delete_id
        server = self.jet_id.server_id or self.server_id
        if plan and server:
            if self._delete_plan_is_busy():
                _logger.info("Delete plan for backup %s is busy; retry later", self.id)
                return
            self.write(
                {"state": "deleting", "operation_token": secrets.token_urlsafe(32)}
            )
            server.sudo().run_flight_plan(
                flight_plan=plan,
                jet=self.jet_id,
                plan_log={
                    **({"waypoint_id": waypoint.id} if waypoint else {}),
                    "backup_id": self.id,
                    "backup_operation": "delete",
                    "backup_token": self.operation_token,
                },
                variable_values=self._get_custom_variable_values(),
            )
        else:
            if plan:
                _logger.warning(
                    "Backup %s has no host; stored data was left in place", self.id
                )
            self._unlink_finished()

    def _plan_finished(self, log):
        """Apply only the result of the operation started for this backup.

        Args:
            log (cx.tower.plan.log): Finished operation log.
        """
        self.ensure_one()
        if log.backup_operation == "restore":
            return
        expected_state = {"backup": "running", "delete": "deleting"}.get(
            log.backup_operation
        )
        if not (
            log.backup_token
            and log.backup_token == self.operation_token
            and self.state == expected_state
        ):
            _logger.warning(
                "Ignored mismatched operation result for backup %s", self.id
            )
            return
        if log.backup_operation == "delete":
            self.write({"operation_token": False})
            if log.plan_status == 0:
                self._unlink_finished()
            else:
                self.write({"state": "delete_failed"})
            return
        success = log.plan_status == 0
        self.write({"state": "done" if success else "failed", "operation_token": False})
        command_log = self.created_from_command_log_id
        if command_log.is_running:
            try:
                with self.env.cr.savepoint():
                    command_log.finish(status=0 if success else BACKUP_CREATE_FAILED)
            except Exception:
                _logger.exception(
                    "Could not finish triggering command for backup %s", self.id
                )

    @api.model
    def _run_cleanup(self):
        """Remove unlinked failed uploads, then excess successful backups."""
        backups = self.sudo()
        backups.search(
            [("state", "=", "failed"), ("waypoint_ids", "=", False)]
        ).unlink()
        templates = (
            self.env["cx.tower.backup.template"].sudo().search([("keep_last", ">", 0)])
        )
        for template in templates:
            successful = backups.search(
                [
                    ("backup_template_id", "=", template.id),
                    ("state", "=", "done"),
                    ("jet_id", "!=", False),
                    ("waypoint_ids", "=", False),
                ]
            )
            for jet_backups in successful.grouped("jet_id").values():
                for backup in jet_backups[template.keep_last :]:
                    if not backup._has_running_restore():
                        backup.unlink()
