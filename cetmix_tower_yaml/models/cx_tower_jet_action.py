# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerJetAction(models.Model):
    _name = "cx.tower.jet.action"
    _inherit = [
        "cx.tower.jet.action",
        "cx.tower.yaml.mixin",
    ]

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "name",
            "note",
            "priority",
            "access_level",
            "state_from_id",
            "state_transit_id",
            "state_to_id",
            "state_error_id",
            "plan_id",
        ]
        return res
