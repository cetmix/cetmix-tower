# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerKeyValue(models.Model):
    _name = "cx.tower.key.value"
    _inherit = [
        "cx.tower.key.value",
        "cx.tower.yaml.mixin",
    ]

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "key_id",
        ]
        return res
