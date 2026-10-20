# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerJetTemplateDependency(models.Model):
    _name = "cx.tower.jet.template.dependency"
    _inherit = [
        "cx.tower.jet.template.dependency",
        "cx.tower.yaml.mixin",
    ]

    template_required_id = fields.Many2one(yaml_export="include")
    state_required_id = fields.Many2one(yaml_export="include")
