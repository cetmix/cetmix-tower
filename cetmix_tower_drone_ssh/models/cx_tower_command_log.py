# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models

from odoo.addons.cetmix_tower_drone.models.constants import (
    JOB_ACTIVE_STATES,
    JOB_STATE_FAILED,
    JOB_STATE_TIMED_OUT,
)
from odoo.addons.cetmix_tower_server.models.constants import (
    COMMAND_TIMED_OUT,
    COMMAND_TIMED_OUT_MESSAGE,
    GENERAL_ERROR,
)

from .constants import NO_DRONE_CONTROLLER


class CxTowerCommandLog(models.Model):
    _inherit = "cx.tower.command.log"

    drone_job_id = fields.Many2one(
        comodel_name="cx.tower.drone.job",
        ondelete="set null",
        copy=False,
        index=True,
        groups="cetmix_tower_base.group_root",
    )
    drone_controller_id = fields.Many2one(
        comodel_name="cx.tower.drone.controller",
        string="Executed on",
        related="drone_job_id.controller_id",
        store=True,
        readonly=True,
        help="Drone controller that holds the command",
    )

    def _on_drone_ssh_done(self, drone_job, result):
        """Finish the log from the drone job outcome.

        Called by the drone module as the user who ran the command.

        Args:
            drone_job (cx.tower.drone.job): Job in its final state.
            result (dict): ``status``, ``response``, ``error``; None for
                a timeout.

        Returns:
            bool: True when the log is finished, False to get the result
                delivered again.
        """
        self.ensure_one()
        if not self.is_running:
            return True
        job = drone_job.sudo()
        if job.state == JOB_STATE_TIMED_OUT:
            self.finish(status=COMMAND_TIMED_OUT, error=COMMAND_TIMED_OUT_MESSAGE)
        else:
            masked = self.server_id._mask_command_result(
                self, result["status"], result["response"], result["error"]
            )
            if job.state == JOB_STATE_FAILED and masked["status"] in (None, 0):
                masked["status"] = (
                    GENERAL_ERROR if job.last_heartbeat else NO_DRONE_CONTROLLER
                )
            self.finish(**masked)
        self.invalidate_recordset(["is_running", "finish_date"])
        return not self.is_running

    def _command_finished(self):
        """Cancel the drone job when the log was ended outside the drone."""
        self.ensure_one()
        job = self.sudo().drone_job_id
        if job and job.state in JOB_ACTIVE_STATES:
            job._cancel()
        return super()._command_finished()
