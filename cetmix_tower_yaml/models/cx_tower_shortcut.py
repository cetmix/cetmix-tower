# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerShortcut(models.Model):
    _name = "cx.tower.shortcut"
    _inherit = ["cx.tower.shortcut", "cx.tower.yaml.mixin"]

    name = fields.Char(yaml_export=True)
    sequence = fields.Integer(yaml_export=True)
    access_level = fields.Selection(yaml_export=True)
    action = fields.Selection(yaml_export=True)
    command_id = fields.Many2one(yaml_export="include")
    use_sudo = fields.Boolean(yaml_export=True)
    plan_id = fields.Many2one(yaml_export="include")
    note = fields.Text(yaml_export=True)
