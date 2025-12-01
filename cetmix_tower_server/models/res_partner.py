# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    server_ids = fields.One2many(
        "cx.tower.server",
        "partner_id",
        string="Servers",
        groups="cetmix_tower_server.group_user",
    )

    server_count = fields.Integer(
        compute="_compute_server_count",
        recursive=True,
    )

    secret_ids = fields.One2many(
        "cx.tower.key.value",
        "partner_id",
        string="Secrets",
        domain=[("key_id.key_type", "=", "s")],
        groups="cetmix_tower_server.group_manager",
    )

    @api.depends("server_ids", "child_ids.server_count")
    def _compute_server_count(self):
        for partner in self:
            own_server_count = len(partner.server_ids)
            child_server_count = sum(partner.child_ids.mapped("server_count"))
            partner.server_count = own_server_count + child_server_count

    def action_view_partner_servers(self):
        """Open server list filtered by partner and all its descendants."""
        self.ensure_one()
        return {
            "name": "Servers",
            "type": "ir.actions.act_window",
            "res_model": "cx.tower.server",
            "view_mode": "kanban,list,form",
            "domain": [("partner_id", "child_of", self.id)],
            "context": {"default_partner_id": self.id},
        }
