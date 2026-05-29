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
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
            "custom_variable_value_ids",
        ]
        return res

    def _get_deferred_x2m_import_fields(self):
        """Return scheduled-task child records resolved after import."""
        return {
            "custom_variable_value_ids": {
                "child_model": "cx.tower.scheduled.task.cv",
                "deferred_field": "variable_value_id",
                "target_model": "cx.tower.variable.value",
                "skip_empty": True,
            }
        }
