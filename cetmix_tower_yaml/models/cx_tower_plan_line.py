# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerPlanLine(models.Model):
    _name = "cx.tower.plan.line"
    _inherit = ["cx.tower.plan.line", "cx.tower.yaml.mixin"]

    sequence = fields.Integer(yaml_export=True)
    condition = fields.Char(yaml_export=True)
    use_sudo = fields.Boolean(yaml_export=True)
    path = fields.Char(yaml_export=True)
    command_id = fields.Many2one(yaml_export="include")
    action_ids = fields.One2many(yaml_export="explode")
    variable_ids = fields.Many2many(yaml_export="include")
