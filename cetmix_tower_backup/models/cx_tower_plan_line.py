# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, models


class CxTowerPlanLine(models.Model):
    _inherit = "cx.tower.plan.line"

    @api.constrains("plan_id", "command_id")
    def _check_backup_plan_line(self):
        """Validate backup plan trees after adding or moving a command line.

        Returns:
            None: Every affected backup execution tree remains at Root level.

        Raises:
            ValidationError: A changed line introduces a non-Root plan or command.
        """
        self.env["cx.tower.plan"]._validate_backup_plan_trees(
            changed_plans=self.sudo().plan_id
        )

    def _run(self, server, plan_log_record, **kwargs):
        """Pass the operation's backup record to Python context builders.

        Args:
            server (cx.tower.server): Execution server.
            plan_log_record (cx.tower.plan.log): Current plan execution.
            **kwargs (dict): Arguments forwarded to the command runner.

        Returns:
            None: Parent runner result.
        """
        log = plan_log_record.sudo()
        backup = log.backup_id
        if not backup and log.waypoint_id._is_backup_waypoint():
            backup = log.waypoint_id.backup_id
        kwargs["backup"] = backup.sudo()
        return super()._run(server, plan_log_record, **kwargs)
