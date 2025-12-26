# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerVariable(models.Model):
    _name = "cx.tower.variable"
    _inherit = ["cx.tower.variable", "cx.tower.yaml.mixin"]

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "name",
            "access_level",
            "variable_type",
            "option_ids",
            "applied_expression",
            "validation_pattern",
            "validation_message",
            "note",
            "tag_ids",
        ]
        return res
