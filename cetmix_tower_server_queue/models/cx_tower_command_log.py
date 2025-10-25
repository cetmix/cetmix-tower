# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models, tools

from odoo.addons.cetmix_tower_server.models.constants import (
    COMMAND_STOPPED,
    COMMAND_TIMED_OUT,
)
from odoo.addons.queue_job.job import CANCELLED


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

    def finish(
        self, finish_date=None, status=None, response=None, error=None, **kwargs
    ):
        if status == COMMAND_TIMED_OUT and self.queue_job_id:
            self.queue_job_id.sudo()._change_job_state(CANCELLED, result=error)

        # Do not update status if it was already stopped
        if self.command_status == COMMAND_STOPPED and status != COMMAND_STOPPED:
            return False

        if status == COMMAND_STOPPED and self.queue_job_id:
            return super().finish(finish_date, status, response, error, **kwargs)

        # Avoid to finish the command log multiple times in the same time
        try:
            with self.env.cr.savepoint(), tools.mute_logger("odoo.sql_db"):
                self.env.cr.execute(
                    f"SELECT command_status FROM {self._table} WHERE id = %s FOR UPDATE NOWAIT",  # noqa: E501
                    [self.id],
                )
        except Exception:
            return {}

        return super().finish(finish_date, status, response, error, **kwargs)
