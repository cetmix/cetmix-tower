# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerServer(models.Model):
    _inherit = "cx.tower.server"

    def _command_runner_wrapper(
        self,
        command,
        log_record,
        rendered_command_code,
        rendered_command_path=None,
        ssh_connection=None,
        **kwargs,
    ):
        # If the flight plan log has an entry on the parent flight plan log,
        # it means that this flight plan was launched from another plan,
        # this plan should be launched as a synchronous command to
        # preserve the order of execution of commands with action “Run flight plan”.
        # Use runner only if command log record is provided.
        if log_record and not log_record.plan_log_id.parent_flight_plan_log_id:
            self.with_delay()._command_runner(
                command,
                log_record,
                rendered_command_code,
                rendered_command_path,
                ssh_connection,
                **kwargs,
            )

        # Otherwise fallback to `super` to return the command output
        else:
            return super()._command_runner_wrapper(
                command,
                log_record,
                rendered_command_code,
                rendered_command_path,
                ssh_connection,
                **kwargs,
            )
