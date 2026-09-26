# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models
from odoo.exceptions import UserError

from odoo.addons.cetmix_tower_drone.models.constants import JOB_ACTIVE_STATES


class CxTowerDroneJob(models.Model):
    _inherit = "cx.tower.drone.job"

    command_log_id = fields.Many2one(
        comodel_name="cx.tower.command.log",
        compute="_compute_command_log_id",
        string="Command log",
        help="Command log that sent this job, including while it is still running",
    )

    def _compute_command_log_id(self):
        logs = (
            self.env["cx.tower.command.log"]
            .sudo()
            .search([("drone_job_id", "in", self.ids)])
        )
        by_job = {log.drone_job_id.id: log.id for log in logs}
        for job in self:
            job.command_log_id = by_job.get(job.id, False)

    def _cancel(self):
        """Stop the command logs of the cancelled jobs.

        The callback is not called for a cancelled job, and drone logs are
        left out of the zombie cron, so nothing else would end them.

        Raises:
            UserError: If a log is locked by another transaction and was
                not stopped. The whole cancellation is rolled back then.
        """
        jobs = self.sudo().filtered(lambda j: j.state in JOB_ACTIVE_STATES)
        result = super()._cancel()
        if jobs:
            logs = (
                self.env["cx.tower.command.log"]
                .sudo()
                .search([("drone_job_id", "in", jobs.ids), ("is_running", "=", True)])
            )
            logs.stop()
            # A locked log is skipped by finish() without an error
            logs.invalidate_recordset(["is_running", "finish_date"])
            if logs.filtered("is_running"):
                raise UserError(
                    self.env._(
                        "The command is being updated right now. "
                        "Try to cancel the job again."
                    )
                )
        return result
