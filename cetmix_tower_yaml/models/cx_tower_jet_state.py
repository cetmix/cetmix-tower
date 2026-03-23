# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerJetState(models.Model):
    _name = "cx.tower.jet.state"
    _inherit = [
        "cx.tower.jet.state",
        "cx.tower.yaml.mixin",
    ]

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "name",
            "sequence",
            "access_level",
            "color",
            "note",
        ]
        return res
