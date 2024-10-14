# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerCommand(models.Model):
    _name = "cx.tower.command"
    _inherit = ["cx.tower.command", "cx.tower.yaml.mixin"]

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        if self.action in ["ssh_command", "python_code"]:
            res += [
                "access_level",
                "allow_parallel_run",
                "path",
                "note",
                "code",
                "action",
            ]
        elif self.action == "file_using_template":
            res += [
                "access_level",
                "allow_parallel_run",
                "path",
                "note",
                "action",
                "file_template_id",
            ]
        return res
