# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerServerLog(models.Model):
    _name = "cx.tower.server.log"
    _inherit = [
        "cx.tower.server.log",
        "cx.tower.yaml.mixin",
    ]

    name = fields.Char(yaml_export=True)
    log_type = fields.Selection(yaml_export=True)
    command_id = fields.Many2one(yaml_export="include")
    use_sudo = fields.Boolean(yaml_export=True)
    file_template_id = fields.Many2one(yaml_export="include")
    file_id = fields.Many2one(yaml_export="reference")
