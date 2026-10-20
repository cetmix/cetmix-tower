# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerJetState(models.Model):
    _name = "cx.tower.jet.state"
    _inherit = [
        "cx.tower.jet.state",
        "cx.tower.yaml.mixin",
    ]

    name = fields.Char(yaml_export=True)
    sequence = fields.Integer(yaml_export=True)
    access_level = fields.Selection(yaml_export=True)
    color = fields.Integer(yaml_export=True)
    note = fields.Text(yaml_export=True)
