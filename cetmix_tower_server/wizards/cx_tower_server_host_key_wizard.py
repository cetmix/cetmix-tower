# Copyright 2025 Cetmix Oy
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).

from odoo import _, fields, models


class CxTowerServerHostKeyWizard(models.TransientModel):
    """Wizard to show host key"""

    _name = "cx.tower.server.host.key.wizard"
    _description = "Show Host Key"

    is_error = fields.Boolean()
    host_key = fields.Char()
    server_id = fields.Many2one("cx.tower.server")

    def action_insert_host_key(self):
        """Show the host key"""
        self.ensure_one()
        self.server_id.write({"host_key": self.host_key, "skip_host_key": False})
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "title": _("Host Key"),
                "message": _("Key inserted successfully!"),
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
