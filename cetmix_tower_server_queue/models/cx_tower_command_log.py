# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from psycopg2.errors import LockNotAvailable

from odoo import fields, models, tools

from odoo.addons.cetmix_tower_server.models.constants import (
    COMMAND_STOPPED,
    COMMAND_TIMED_OUT,
)
from odoo.addons.queue_job.job import CANCELLED

_logger = logging.getLogger(__name__)


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
        """Finish the command log

        Args:
            finish_date (Datetime, optional): Command finish date. Defaults to None.
            status (Integer, optional): Command status. Defaults to None.
            response (Text, optional): Command response. Defaults to None.
            error (Text, optional): Command error. Defaults to None.
        """

        # Filter out command logs that are already stopped
        command_logs_to_process = self.filtered(
            lambda log: log.command_status != COMMAND_STOPPED
        )
        if not command_logs_to_process:
            return

        # Lock and process each record individually
        locked_logs = self.browse()
        for command_log in command_logs_to_process:
            try:
                with self.env.cr.savepoint(), tools.mute_logger("odoo.sql_db"):
                    self.env.cr.execute(
                        f"SELECT command_status FROM {self._table} WHERE id = %s FOR UPDATE NOWAIT",  # noqa: E501
                        (command_log.id,),
                    )
                    locked_logs |= command_log
            except LockNotAvailable as e:
                _logger.warning(
                    "Could not acquire lock on command log %s, skipping: %s",
                    command_log.id,
                    e,
                )
                continue

        if not locked_logs:
            return

        # Update the related queue job state if the command timed out
        if status == COMMAND_TIMED_OUT:
            for command_log in locked_logs:
                if command_log.queue_job_id:
                    command_log.queue_job_id.sudo()._change_job_state(
                        CANCELLED, result=error
                    )

        return super(CxTowerCommandLog, locked_logs).finish(
            finish_date, status, response, error, **kwargs
        )
