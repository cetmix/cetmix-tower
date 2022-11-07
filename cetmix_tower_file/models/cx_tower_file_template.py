# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CxTowerFileTemplate(models.Model):
    _name = "cx.tower.file.template"
    _description = "Cx Tower File Template"

    name = fields.Char(help="Template Name")
    file_name = fields.Char(
        help="Default full file name with file type for example: test.txt",
    )
    code = fields.Text(string="Code")
    server_dir = fields.Char(string="Directory on server")
    file_ids = fields.One2many("cx.tower.file", "template_id")
    tag_ids = fields.Many2many(
        comodel_name="cx.tower.tag",
        relation="cx_tower_file_template_tag_rel",
        column1="file_template_id",
        column2="tag_id",
        string="Tags",
    )

    def write(self, vals):
        """
        Override to update files related with the templates
        """
        result = super(CxTowerFileTemplate, self).write(vals)
        for file in self.mapped("file_ids"):
            file.write(file._get_file_values_from_related_template())
        return result
