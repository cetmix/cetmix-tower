# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerOs(models.Model):
    _name = "cx.tower.os"
    _inherit = [
        "cx.tower.os",
        "cx.tower.yaml.mixin",
    ]

    name = fields.Char(yaml_export=True)
    color = fields.Integer(yaml_export=True)
    parent_id = fields.Many2one(yaml_export="include")
