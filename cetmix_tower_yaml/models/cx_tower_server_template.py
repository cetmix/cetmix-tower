# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerServerTemplate(models.Model):
    _name = "cx.tower.server.template"
    _inherit = [
        "cx.tower.server.template",
        "cx.tower.yaml.mixin",
    ]

    name = fields.Char(yaml_export=True)
    color = fields.Integer(yaml_export=True)
    os_id = fields.Many2one(yaml_export="include")
    tag_ids = fields.Many2many(yaml_export="include")
    note = fields.Text(yaml_export=True)
    ssh_port = fields.Integer(yaml_export=True)
    ssh_username = fields.Char(yaml_export=True)
    ssh_key_id = fields.Many2one(yaml_export="include")
    ssh_auth_mode = fields.Selection(yaml_export=True)
    use_sudo = fields.Selection(yaml_export=True)
    variable_value_ids = fields.One2many(yaml_export="explode")
    server_log_ids = fields.One2many(yaml_export="explode")
    shortcut_ids = fields.Many2many(yaml_export="include")
    scheduled_task_ids = fields.Many2many(yaml_export="include")
    flight_plan_id = fields.Many2one(yaml_export="include")
    plan_delete_id = fields.Many2one(yaml_export="include")

    def _get_force_x2m_resolve_models(self):
        res = super()._get_force_x2m_resolve_models()

        # Add Flight Plan in order to always try to use existing one
        # This is useful to avoid duplicating existing plans
        res += ["cx.tower.plan", "cx.tower.shortcut", "cx.tower.scheduled.task"]
        return res
