# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerVariableValue(models.Model):
    _name = "cx.tower.variable.value"
    _inherit = ["cx.tower.variable.value", "cx.tower.yaml.mixin"]

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "sequence",
            "access_level",
            "variable_id",
            "value_char",
            "variable_ids",
            "required",
        ]
        return res
