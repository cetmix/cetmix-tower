# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerFileTemplate(models.Model):
    _name = "cx.tower.file.template"
    _description = "Cx Tower File Template"

    def _compute_file_count(self):
        """
        Compute total template files
        """
        for template in self:
            template.file_count = len(template.file_ids)

    name = fields.Char(help="Template Name")
    file_name = fields.Char(
        help="Default full file name with file type for example: test.txt",
    )
    code = fields.Text(string="File content")
    server_dir = fields.Char(string="Directory on server")
    file_ids = fields.One2many("cx.tower.file", "template_id")
    file_count = fields.Integer(
        "File(s)",
        compute="_compute_file_count",
    )
    tag_ids = fields.Many2many(
        comodel_name="cx.tower.tag",
        relation="cx_tower_file_template_tag_rel",
        column1="file_template_id",
        column2="tag_id",
        string="Tags",
    )
    note = fields.Text(help="This field is used to put some notes regarding template.")

    def write(self, vals):
        """
        Override to update files related with the templates
        """
        result = super(CxTowerFileTemplate, self).write(vals)
        for file in self.mapped("file_ids"):
            file.write(file._get_file_values_from_related_template())
        return result

    def action_open_files(self):
        """
        Open current template files
        """
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.cx_tower_file_action"
        )
        action["domain"] = [("id", "in", self.file_ids.ids)]
        return action
