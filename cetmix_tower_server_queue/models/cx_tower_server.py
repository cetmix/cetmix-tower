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
        # Use runner only if command log record is provided
        if log_record:
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
