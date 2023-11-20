# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerServer(models.Model):
    _inherit = "cx.tower.server"

    # Use job que to run commands on server
    def execute_commands(self, commands, sudo=None, **kwargs):
        # Get variables from commands {command.id: [variables]}
        variables = commands.get_variables()

        # Run pre-command hook
        commands, variables, sudo, kwargs = self._pre_execute_commands(
            commands, variables, sudo, **kwargs
        )

        # Execute commands
        for server in self:
            server.with_delay()._execute_commands_on_server(
                commands, variables, sudo, **kwargs
            )
