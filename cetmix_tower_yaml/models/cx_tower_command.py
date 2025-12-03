# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerCommand(models.Model):
    _name = "cx.tower.command"
    _inherit = ["cx.tower.command", "cx.tower.yaml.mixin"]

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "access_level",
            "name",
            "action",
            "allow_parallel_run",
            "note",
            "os_ids",
            "tag_ids",
            "path",
            "file_template_id",
            "flight_plan_id",
            "code",
            "server_status",
            "variable_ids",
            "secret_ids",
            "no_split_for_sudo",
            "if_file_exists",
            "disconnect_file",
        ]
        return res
