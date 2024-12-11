# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, models


class CxTowerServerTemplate(models.Model):
    _name = "cx.tower.server.template"
    _inherit = [
        "cx.tower.server.template",
        "cx.tower.yaml.mixin",
    ]

    SSH_PASSWORD_MASK = "********"

    @api.model_create_multi
    def create(self, vals_list):
        # Check secret value before creating a record
        for vals in vals_list:
            if "ssh_password" in vals:
                self._check_secret_value_for_placeholder(
                    vals["ssh_password"], self.SSH_PASSWORD_MASK
                )
        return super().create(vals_list)

    def write(self, vals):
        # Check secret value before updating a record
        if "ssh_password" in vals:
            self._check_secret_value_for_placeholder(
                vals["ssh_password"], self.SSH_PASSWORD_MASK
            )
        return super().write(vals)

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

    def _get_force_x2m_resolve_models(self):
        res = super()._get_force_x2m_resolve_models()

        # Add Flight Plan in order to always try to use existing one
        # This is useful to avoid duplicating existing plans
        res.append("cx.tower.plan")
        return res
