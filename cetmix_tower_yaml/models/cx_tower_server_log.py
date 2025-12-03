# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerServerLog(models.Model):
    _name = "cx.tower.server.log"
    _inherit = [
        "cx.tower.server.log",
        "cx.tower.yaml.mixin",
    ]

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "name",
            "log_type",
            "command_id",
            "use_sudo",
            "file_template_id",
            "file_id",
        ]
        return res
