# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerJetAction(models.Model):
    _name = "cx.tower.jet.action"
    _inherit = [
        "cx.tower.jet.action",
        "cx.tower.yaml.mixin",
    ]

    name = fields.Char(yaml_export=True)
    note = fields.Text(yaml_export=True)
    priority = fields.Integer(yaml_export=True)
    access_level = fields.Selection(yaml_export=True)
    state_from_id = fields.Many2one(yaml_export="include")
    state_transit_id = fields.Many2one(yaml_export="include")
    state_to_id = fields.Many2one(yaml_export="include")
    state_error_id = fields.Many2one(yaml_export="include")
    plan_id = fields.Many2one(yaml_export="include")
