# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerPlan(models.Model):
    _name = "cx.tower.plan"
    _inherit = ["cx.tower.plan", "cx.tower.yaml.mixin"]

    name = fields.Char(yaml_export=True)
    access_level = fields.Selection(yaml_export=True)
    allow_parallel_run = fields.Boolean(yaml_export=True)
    color = fields.Integer(yaml_export=True)
    tag_ids = fields.Many2many(yaml_export="include")
    note = fields.Text(yaml_export=True)
    on_error_action = fields.Selection(yaml_export=True)
    custom_exit_code = fields.Integer(yaml_export=True)
    line_ids = fields.One2many(yaml_export="explode")
