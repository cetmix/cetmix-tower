# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerTag(models.Model):
    _name = "cx.tower.tag"
    _inherit = [
        "cx.tower.reference.mixin",
    ]
    _description = "Cetmix Tower Tag"

    server_ids = fields.Many2many(
        comodel_name="cx.tower.server",
        relation="cx_tower_server_tag_rel",
        column1="tag_id",
        column2="server_id",
        string="Servers",
    )
    color = fields.Integer(help="For better visualization in views")
