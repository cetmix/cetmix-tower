# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerVariable(models.Model):
    _name = "cx.tower.variable"
    _inherit = ["cx.tower.variable", "cx.tower.yaml.mixin"]

    name = fields.Char(yaml_export=True)
    access_level = fields.Selection(yaml_export=True)
    variable_type = fields.Selection(yaml_export=True)
    option_ids = fields.One2many(yaml_export="explode")
    applied_expression = fields.Text(yaml_export=True)
    validation_pattern = fields.Char(yaml_export=True)
    validation_message = fields.Char(yaml_export=True)
    note = fields.Text(yaml_export=True)
    tag_ids = fields.Many2many(yaml_export="include")
