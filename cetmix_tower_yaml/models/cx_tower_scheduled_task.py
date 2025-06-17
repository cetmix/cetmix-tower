# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerScheduledTask(models.Model):
    _name = "cx.tower.scheduled.task"
    _inherit = ["cx.tower.scheduled.task", "cx.tower.yaml.mixin"]

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "name",
            "sequence",
            "action",
            "command_id",
            "plan_id",
            "interval_number",
            "interval_type",
            "next_call",
            "last_call",
        ]
        return res
