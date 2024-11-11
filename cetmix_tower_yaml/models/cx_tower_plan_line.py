# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerPlanLine(models.Model):
    _name = "cx.tower.plan.line"
    _inherit = ["cx.tower.plan.line", "cx.tower.yaml.mixin"]

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "sequence",
            "condition",
            "use_sudo",
            "path",
            "command_id",
            "action_ids",
            "variable_ids",
        ]
        return res
