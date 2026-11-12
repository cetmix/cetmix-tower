# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


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

    def _plan_finished(self):
        """Apply backup state before Tower finishes its waypoint callback.

        Returns:
            bool: Parent completion-hook result.
        """
        result = super()._plan_finished()
        log = self.sudo()
        if log.backup_id and not log.parent_flight_plan_log_id:
            log.backup_id._plan_finished(log)
        return result
