# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerFileTemplate(models.Model):
    _name = "cx.tower.file.template"
    _inherit = ["cx.tower.file.template", "cx.tower.yaml.mixin"]

    name = fields.Char(yaml_export=True)
    source = fields.Selection(yaml_export=True)
    file_type = fields.Selection(yaml_export=True)
    server_dir = fields.Char(yaml_export=True)
    file_name = fields.Char(yaml_export=True)
    keep_when_deleted = fields.Boolean(yaml_export=True)
    tag_ids = fields.Many2many(yaml_export="include")
    note = fields.Text(yaml_export=True)
    code = fields.Text(yaml_export=True)
    variable_ids = fields.Many2many(yaml_export="include")
    secret_ids = fields.Many2many(yaml_export="include")
