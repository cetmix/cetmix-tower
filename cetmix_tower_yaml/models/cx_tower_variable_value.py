# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerVariableValue(models.Model):
    _name = "cx.tower.variable.value"
    _inherit = ["cx.tower.variable.value", "cx.tower.yaml.mixin"]

    sequence = fields.Integer(yaml_export=True)
    access_level = fields.Selection(yaml_export=True)
    variable_id = fields.Many2one(yaml_export="include")
    value_char = fields.Char(yaml_export=True)
    variable_ids = fields.Many2many(yaml_export="include")
    required = fields.Boolean(yaml_export=True)
