# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerVariableOption(models.Model):
    _name = "cx.tower.variable.option"
    _inherit = ["cx.tower.variable.option", "cx.tower.yaml.mixin"]

    sequence = fields.Integer(yaml_export=True)
    access_level = fields.Selection(yaml_export=True)
    name = fields.Char(yaml_export=True)
    value_char = fields.Char(yaml_export=True)
