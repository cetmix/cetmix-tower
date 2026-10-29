# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerServer(models.Model):
    _name = "cx.tower.server"
    _inherit = [
        "cx.tower.server",
        "cx.tower.yaml.mixin",
    ]

    name = fields.Char(yaml_export=True)
    ip_v4_address = fields.Char(yaml_export=True)
    ip_v6_address = fields.Char(yaml_export=True)
    skip_host_key = fields.Boolean(yaml_export=True)
    color = fields.Integer(yaml_export=True)
    os_id = fields.Many2one(yaml_export="include")
    tag_ids = fields.Many2many(yaml_export="include")
    url = fields.Char(yaml_export=True)
    note = fields.Text(yaml_export=True)
    ssh_port = fields.Integer(yaml_export=True)
    ssh_username = fields.Char(yaml_export=True)
    ssh_key_id = fields.Many2one(yaml_export="include")
    ssh_auth_mode = fields.Selection(yaml_export=True)
    use_sudo = fields.Selection(yaml_export=True)
    variable_value_ids = fields.One2many(yaml_export="explode")
    secret_ids = fields.One2many(yaml_export="explode")
    server_log_ids = fields.One2many(yaml_export="explode")
    shortcut_ids = fields.Many2many(yaml_export="include")
    scheduled_task_ids = fields.Many2many(yaml_export="include")
    plan_delete_id = fields.Many2one(yaml_export="include")
    file_ids = fields.One2many(yaml_export="explode")
    command_ids = fields.Many2many(yaml_export="include")
    plan_ids = fields.Many2many(yaml_export="include")

    def _get_force_x2m_resolve_models(self):
        res = super()._get_force_x2m_resolve_models()

        # This is useful to avoid duplicating existing plans
        res += [
            "cx.tower.shortcut",
            "cx.tower.scheduled.task",
            "cx.tower.command",
            "cx.tower.plan",
        ]
        return res
