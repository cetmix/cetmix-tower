# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerShortcut(models.Model):
    _name = "cx.tower.shortcut"
    _inherit = ["cx.tower.shortcut", "cx.tower.yaml.mixin"]

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "name",
            "sequence",
            "access_level",
            "action",
            "command_id",
            "use_sudo",
            "plan_id",
            "note",
        ]
        return res
