# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerPlanLineAction(models.Model):
    _name = "cx.tower.plan.line.action"
    _inherit = ["cx.tower.plan.line.action", "cx.tower.yaml.mixin"]

    sequence = fields.Integer(yaml_export=True)
    condition = fields.Selection(yaml_export=True)
    value_char = fields.Char(yaml_export=True)
    action = fields.Selection(yaml_export=True)
    custom_exit_code = fields.Integer(yaml_export=True)
    variable_value_ids = fields.One2many(yaml_export="explode")
