# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerJetTemplateDependency(models.Model):
    _name = "cx.tower.jet.template.dependency"
    _inherit = [
        "cx.tower.jet.template.dependency",
        "cx.tower.yaml.mixin",
    ]

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "template_required_id",
            "state_required_id",
        ]
        return res
