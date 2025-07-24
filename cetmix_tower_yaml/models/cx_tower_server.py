# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerServer(models.Model):
    _name = "cx.tower.server"
    _inherit = [
        "cx.tower.server",
        "cx.tower.yaml.mixin",
    ]

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "name",
            "ip_v4_address",
            "ip_v6_address",
            "skip_host_key",
            "color",
            "os_id",
            "tag_ids",
            "url",
            "note",
            "ssh_port",
            "ssh_username",
            "ssh_key_id",
            "ssh_auth_mode",
            "use_sudo",
            "variable_value_ids",
            "secret_ids",
            "server_log_ids",
            "shortcut_ids",
            "scheduled_task_ids",
            "plan_delete_id",
            "file_ids",
            "command_ids",
            "plan_ids",
        ]
        return res

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
