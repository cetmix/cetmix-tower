# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerOs(models.Model):
    """Operating System"""

    _name = "cx.tower.os"
    _inherit = [
        "cx.tower.reference.mixin",
    ]
    _description = "Cetmix Tower Operating System"
    _order = "name"

    color = fields.Integer(help="For better visualization in views")
    parent_id = fields.Many2one(string="Previous Version", comodel_name="cx.tower.os")
