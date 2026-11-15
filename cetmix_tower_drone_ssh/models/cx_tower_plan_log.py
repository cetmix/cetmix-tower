# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class CxTowerPlanLog(models.Model):
    _inherit = "cx.tower.plan.log"

    def unlink(self):
        """Delete the finished drone jobs of the deleted flight plan logs.

        Command logs and nested flight plan logs are deleted by the
        database (``ondelete="cascade"``), so ``unlink()`` of the command
        log does not run for them. Their jobs are collected here, before
        the logs are deleted.

        Returns:
            bool: Result of the parent ``unlink()``.
        """
        plan_logs = self.sudo()
        nested_plan_logs = plan_logs
        while nested_plan_logs:
            nested_plan_logs = (
                plan_logs.search(
                    [("parent_flight_plan_log_id", "in", nested_plan_logs.ids)]
                )
                - plan_logs
            )
            plan_logs |= nested_plan_logs
        drone_jobs = plan_logs.command_log_ids._get_finished_drone_jobs()
        res = super().unlink()
        drone_jobs.unlink()
        return res
