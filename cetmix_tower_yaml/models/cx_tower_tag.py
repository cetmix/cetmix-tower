# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerTag(models.Model):
    _name = "cx.tower.tag"
    _inherit = ["cx.tower.tag", "cx.tower.yaml.mixin"]

    name = fields.Char(yaml_export=True)
    color = fields.Integer(yaml_export=True)
