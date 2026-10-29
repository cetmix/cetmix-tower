# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerKey(models.Model):
    _name = "cx.tower.key"
    _inherit = [
        "cx.tower.key",
        "cx.tower.yaml.mixin",
    ]

    name = fields.Char(yaml_export=True)
    key_type = fields.Selection(yaml_export=True)
    note = fields.Text(yaml_export=True)
