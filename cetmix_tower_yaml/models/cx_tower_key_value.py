# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerKeyValue(models.Model):
    _name = "cx.tower.key.value"
    _inherit = [
        "cx.tower.key.value",
        "cx.tower.yaml.mixin",
    ]

    key_id = fields.Many2one(yaml_export="include")
