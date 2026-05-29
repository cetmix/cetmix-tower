# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerKey(models.Model):
    _name = "cx.tower.key"
    _inherit = [
        "cx.tower.key",
        "cx.tower.yaml.mixin",
    ]

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "name",
            "key_type",
            "note",
        ]
        return res
