# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    server_ids = fields.One2many(
        string="Servers",
        comodel_name="cx.tower.server",
        inverse_name="partner_id",
        help="Cetmix Tower servers that belong to this partner",
    )
