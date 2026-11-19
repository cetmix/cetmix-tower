# Copyright Cetmix OÜ 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class CxTowerServer(models.Model):
    _inherit = "cx.tower.server"

    def _get_terminal_connection_values(self):
        """Return the SSH values for a terminal, after checking access.

        The values themselves are read with `sudo()`, so the right to use this
        server has to be established first. It is checked here, and not only
        when the session record is created, because a session can sit unopened
        while access changes.

        Returns:
            dict: What `SSHConnection` needs to reach this server.
        """
        self.ensure_one()
        self.check_access("read")
        return self._get_ssh_connection_values()

    def action_open_terminal(self):
        """Open an interactive terminal on this server.

        Returns:
            dict: Client action that renders the terminal.
        """
        self.ensure_one()
        return self.env["cx.tower.terminal.session"].action_open_for_server(self.id)
