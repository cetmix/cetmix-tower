# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerScheduledTaskCv(models.Model):
    _name = "cx.tower.scheduled.task.cv"
    _inherit = [
        "cx.tower.scheduled.task.cv",
        "cx.tower.yaml.mixin",
        "cx.tower.reference.mixin",
    ]

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += ["variable_value_id"]
        return res

    def _post_process_yaml_dict_values(self, values):
        """Populate required child fields from the linked variable value."""
        res = super()._post_process_yaml_dict_values(values)
        variable_value_id = res.get("variable_value_id")
        if variable_value_id:
            variable_value = self.env["cx.tower.variable.value"].browse(
                variable_value_id
            )
            if variable_value.exists():
                res.update(
                    {
                        "name": variable_value.name,
                        "variable_id": variable_value.variable_id.id,
                        "option_id": variable_value.option_id.id or False,
                        "value_char": variable_value.value_char,
                    }
                )
        return res
