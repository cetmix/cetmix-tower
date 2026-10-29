# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerScheduledTask(models.Model):
    _name = "cx.tower.scheduled.task"
    _inherit = ["cx.tower.scheduled.task", "cx.tower.yaml.mixin"]

    name = fields.Char(yaml_export=True)
    sequence = fields.Integer(yaml_export=True)
    action = fields.Selection(yaml_export=True)
    command_id = fields.Many2one(yaml_export="include")
    plan_id = fields.Many2one(yaml_export="include")
    interval_number = fields.Integer(yaml_export=True)
    interval_type = fields.Selection(yaml_export=True)
    next_call = fields.Datetime(yaml_export=True)
    last_call = fields.Datetime(yaml_export=True)
    monday = fields.Boolean(yaml_export=True)
    tuesday = fields.Boolean(yaml_export=True)
    wednesday = fields.Boolean(yaml_export=True)
    thursday = fields.Boolean(yaml_export=True)
    friday = fields.Boolean(yaml_export=True)
    saturday = fields.Boolean(yaml_export=True)
    sunday = fields.Boolean(yaml_export=True)
    custom_variable_value_ids = fields.One2many(yaml_export="explode")
