# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerJetWaypointTemplate(models.Model):
    _name = "cx.tower.jet.waypoint.template"
    _inherit = [
        "cx.tower.jet.waypoint.template",
        "cx.tower.yaml.mixin",
    ]

    name = fields.Char(yaml_export=True)
    sequence = fields.Integer(yaml_export=True)
    access_level = fields.Selection(yaml_export=True)
    jet_template_id = fields.Many2one(yaml_export="reference")
    plan_create_id = fields.Many2one(yaml_export="include")
    plan_arrive_id = fields.Many2one(yaml_export="include")
    plan_leave_id = fields.Many2one(yaml_export="include")
    plan_delete_id = fields.Many2one(yaml_export="include")
    note = fields.Text(yaml_export=True)
