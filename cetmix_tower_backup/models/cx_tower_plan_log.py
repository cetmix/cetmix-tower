# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class CxTowerPlanLog(models.Model):
    _inherit = "cx.tower.plan.log"

    backup_id = fields.Many2one(
        "cx.tower.backup",
        ondelete="set null",
        readonly=True,
        index=True,
        groups="cetmix_tower_base.group_root",
    )
    backup_operation = fields.Selection(
        [("backup", "Backup"), ("restore", "Restore"), ("delete", "Delete")],
        readonly=True,
        groups="cetmix_tower_base.group_root",
    )
    backup_token = fields.Char(
        readonly=True, copy=False, groups="cetmix_tower_base.group_root"
    )
    has_backup_values = fields.Boolean(
        readonly=True, index=True, groups="cetmix_tower_base.group_root"
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Mark backup provenance independently of editable custom values.

        Args:
            vals_list (list[dict]): Initial log values.

        Returns:
            cx.tower.plan.log: New logs with provenance flags.
        """
        parents = self.sudo().browse(
            [
                vals["parent_flight_plan_log_id"]
                for vals in vals_list
                if vals.get("parent_flight_plan_log_id")
            ]
        )
        waypoints = (
            self.env["cx.tower.jet.waypoint"]
            .sudo()
            .browse(
                [vals["waypoint_id"] for vals in vals_list if vals.get("waypoint_id")]
            )
        )
        protected_parents = set(parents.filtered("has_backup_values").ids)
        protected_waypoints = set(
            waypoints.filtered(lambda waypoint: waypoint._is_backup_waypoint()).ids
        )
        for vals in vals_list:
            vals["has_backup_values"] = bool(
                vals.get("backup_id")
                or vals.get("parent_flight_plan_log_id") in protected_parents
                or vals.get("waypoint_id") in protected_waypoints
            )
        return super().create(vals_list)

    @api.private
    def finish(self, *args, **kwargs):
        """Apply terminal backup results even when a post-finish hook was skipped.

        Args:
            *args (tuple): Positional arguments forwarded to the parent.
            **kwargs (dict): Keyword arguments forwarded to the parent.

        Returns:
            None: Parent completion result.
        """
        result = super().finish(*args, **kwargs)
        self._finalize_backup_result()
        return result

    def _finalize_backup_result(self):
        """Synchronize only the operation identified by this terminal plan log.

        Returns:
            None: The matching backup is finalized, or the log is inapplicable.
        """
        self.ensure_one()
        log = self.sudo().exists()
        if not log:
            return
        backup = log.backup_id.exists()
        expected = {"backup": "running", "delete": "deleting"}.get(log.backup_operation)
        if (
            backup
            and not log.parent_flight_plan_log_id
            and not log.is_running
            and log.finish_date
            and log.backup_token
            and log.backup_token == backup.operation_token
            and backup.state == expected
        ):
            backup._plan_finished(log)

    def _plan_finished(self):
        """Finalize backup state before notifications and waypoint continuation.

        Returns:
            bool: Parent hook result, or False if a noncritical parent hook fails.
        """
        log = self.sudo()
        if not log.backup_id or log.parent_flight_plan_log_id:
            return super()._plan_finished()
        self._finalize_backup_result()
        try:
            with self.env.cr.savepoint():
                return super()._plan_finished()
        except Exception:
            _logger.exception(
                "Parent completion hook failed for backup plan log %s", self.id
            )
            return False

    @api.model
    def _reconcile_backup_operations(self):
        """Recover missed completion callbacks without guessing from elapsed time.

        Returns:
            None: Matching terminal results are applied independently; errors retry
                on the next run without preventing other backups from recovering.
        """
        logs = (
            self.sudo()
            .with_context(active_test=False)
            .search(
                [
                    ("backup_id.state", "in", ["running", "deleting"]),
                    ("backup_operation", "in", ["backup", "delete"]),
                    ("backup_token", "!=", False),
                    ("parent_flight_plan_log_id", "=", False),
                    ("is_running", "=", False),
                    ("finish_date", "!=", False),
                ]
            )
        )
        for log in logs:
            try:
                with self.env.cr.savepoint():
                    log._finalize_backup_result()
            except Exception:
                _logger.exception(
                    "Could not reconcile backup plan log %s; will retry", log.id
                )
