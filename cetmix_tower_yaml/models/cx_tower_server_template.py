# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerServerTemplate(models.Model):
    _name = "cx.tower.server.template"
    _inherit = [
        "cx.tower.server.template",
        "cx.tower.yaml.mixin",
    ]

    SSH_PASSWORD_MASK = "********"

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
            "ssh_password",
            "ssh_key_id",
            "ssh_auth_mode",
            "use_sudo",
            "variable_value_ids",
            "server_log_ids",
            "flight_plan_id",
        ]
        return res

    def _prepare_record_for_yaml(self):
        res = super()._prepare_record_for_yaml()

        # Replace SSH password with mask
        if res.get("ssh_password"):
            res["ssh_password"] = self.SSH_PASSWORD_MASK
        return res
