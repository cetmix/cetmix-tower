# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerJetTemplate(models.Model):
    _name = "cx.tower.jet.template"
    _inherit = [
        "cx.tower.jet.template",
        "cx.tower.yaml.mixin",
    ]

    name = fields.Char(yaml_export=True)
    note = fields.Text(yaml_export=True)
    tag_ids = fields.Many2many(yaml_export="include")
    limit_per_server = fields.Integer(yaml_export=True)
    show_in_create_wizard = fields.Boolean(yaml_export=True)
    plan_install_id = fields.Many2one(yaml_export="include")
    plan_uninstall_id = fields.Many2one(yaml_export="include")
    plan_clone_same_server_id = fields.Many2one(yaml_export="include")
    plan_clone_different_server_id = fields.Many2one(yaml_export="include")
    variable_value_ids = fields.One2many(yaml_export="explode")
    action_ids = fields.One2many(yaml_export="explode")
    template_requires_ids = fields.One2many(yaml_export="explode")
    waypoint_template_ids = fields.One2many(yaml_export="explode")
    server_log_ids = fields.One2many(yaml_export="explode")
    scheduled_task_ids = fields.Many2many(yaml_export="include")
