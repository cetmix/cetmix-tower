# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerServerTemplate(models.Model):
    _name = "cx.tower.server.template"
    _inherit = [
        "cx.tower.server.template",
        "cx.tower.yaml.mixin",
    ]

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "name",
            "color",
            "os_id",
            "tag_ids",
            "note",
            "ssh_port",
            "ssh_username",
            "ssh_key_id",
            "ssh_auth_mode",
            "use_sudo",
            "variable_value_ids",
            "server_log_ids",
            "shortcut_ids",
            "scheduled_task_ids",
            "flight_plan_id",
            "plan_delete_id",
        ]
        return res

    def _get_force_x2m_resolve_models(self):
        res = super()._get_force_x2m_resolve_models()

        # Add Flight Plan in order to always try to use existing one
        # This is useful to avoid duplicating existing plans
        res += ["cx.tower.plan", "cx.tower.shortcut", "cx.tower.scheduled.task"]
        return res
