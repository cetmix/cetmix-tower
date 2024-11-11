# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerPlan(models.Model):
    _name = "cx.tower.plan"
    _inherit = ["cx.tower.plan", "cx.tower.yaml.mixin"]

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "name",
            "access_level",
            "allow_parallel_run",
            "color",
            "tag_ids",
            "note",
            "on_error_action",
            "custom_exit_code",
            "line_ids",
        ]
        return res
