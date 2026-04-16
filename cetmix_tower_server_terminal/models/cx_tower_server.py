# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class CxTowerServer(models.Model):
    _inherit = "cx.tower.server"

    def action_open_terminal(self):
        """Open an interactive SSH terminal for the current server."""
        self.ensure_one()
        return self.env["cx.tower.terminal.session"].action_open_for_server(self.id)
