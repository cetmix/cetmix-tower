# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerServer(models.Model):
    _inherit = "cx.tower.server"

    def _command_runner_wrapper(
        self, command, log_record, rendered_command_code, ssh_connection=None
    ):
        self.with_delay()._command_runner(
            command, log_record, rendered_command_code, ssh_connection
        )
