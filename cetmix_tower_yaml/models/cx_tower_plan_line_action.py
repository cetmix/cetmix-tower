# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerPlanLineAction(models.Model):
    _name = "cx.tower.plan.line.action"
    _inherit = ["cx.tower.plan.line.action", "cx.tower.yaml.mixin"]

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "sequence",
            "condition",
            "value_char",
            "action",
            "custom_exit_code",
            "variable_value_ids",
        ]
        return res
