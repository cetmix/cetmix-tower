# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models

from odoo.addons.cetmix_tower_server.models.constants import (
    COMMAND_STOPPED,
    COMMAND_TIMED_OUT,
)
from odoo.addons.queue_job.job import CANCELLED, DONE, FAILED


class CxTowerCommandLog(models.Model):
    _inherit = "cx.tower.command.log"

    queue_job_id = fields.Many2one(
        "queue.job",
        readonly=True,
        groups="queue_job.group_queue_job_manager",
    )

    command_status = fields.Integer(
        help="0 if command finished successfully.\n"
        "-100 general error,\n"
        "-101 not found,\n"
        "-201 another instance of this command is running,\n"
        "-202 no runner found for the command action,\n"
        "-203 Python code execution failed\n"
        "-205 plan line condition check failed\n"
        "503 if SSH connection error occurred\n"
        "601 if queue job failed"
    )

    def _command_finished(self):
        """Cancel the queue job after a stop or timeout write has succeeded.

        Runs only for logs core ``finish()`` actually wrote, so a
        concurrent success that won ``FOR UPDATE NOWAIT`` is not
        cancelled. ``queue_job_id`` is group-restricted; read it with
        sudo so a Tower user without the queue-job manager group still
        cancels the job.

        Returns:
            bool: True if the event was handled.
        """
        self.ensure_one()
        job = self.sudo().queue_job_id
        if (
            job
            and self.command_status in (COMMAND_STOPPED, COMMAND_TIMED_OUT)
            and job.state not in (DONE, CANCELLED, FAILED)
        ):
            job._change_job_state(CANCELLED, result=self.command_error)
        return super()._command_finished()
