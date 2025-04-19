# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerVariableOption(models.Model):
    _name = "cx.tower.variable.option"
    _inherit = ["cx.tower.variable.option", "cx.tower.yaml.mixin"]

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "sequence",
            "access_level",
            "name",
            "value_char",
        ]
        return res
