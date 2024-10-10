# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, fields, models
from odoo.exceptions import ValidationError

from .cx_tower_file import TEMPLATE_FILE_FIELD_MAPPING


class CxTowerFileTemplate(models.Model):
    _name = "cx.tower.file.template"
    _inherit = ["cx.tower.reference.mixin"]
    _description = "Cx Tower File Template"

    def _compute_file_count(self):
        """
        Compute total template files
        """
        for template in self:
            template.file_count = len(template.file_ids)

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
    keep_when_deleted = fields.Boolean(
        help="File will be kept on server when deleted in Tower",
    )
    file_type = fields.Selection(
        selection=lambda self: self.env["cx.tower.file"]._selection_file_type(),
        default=lambda self: self.env["cx.tower.file"]._default_file_type(),
        required=True,
    )
    source = fields.Selection(
        [
            ("tower", "Tower"),
            ("server", "Server"),
        ],
        required=True,
        default="tower",
    )
    readonly = fields.Boolean(copy=False, readonly=True)

    def write(self, vals):
        """
        Override to update files related with the templates
        """
        result = super(CxTowerFileTemplate, self).write(vals)
        if any([field_ in vals for field_ in TEMPLATE_FILE_FIELD_MAPPING]):
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

    def create_file(self, server, server_dir="", raise_if_exists=False):
        """
        Create a new file using the current template for the selected server.
        If the same file already exists, just ignore it or raise an error based on the
        parameter.

        :param server: recordset
            The server (cx.tower.server) on which the file should be created. This is a
            required parameter.
        :param server_dir: str, optional
            The directory on the server where the file should be created. If not set,
            the server_dir field of the template will be used.
        :param raise_if_exists: bool, optional
            If set to True, raises a ValidationError if the file already exists on the
            server. Defaults to False.

        :return: cx.tower.file
            Returns the newly created file record (cx.tower.file) if the file was
            created successfully. Returns the existing file record if the file already
            exists and raise_if_exists is False.

        :raises ValidationError:
            If the file already exists on the server and raise_if_exists is True.
        """
        self.ensure_one()
        file_model = self.env["cx.tower.file"]
        existing_file = file_model.search(
            [
                ("template_id", "=", self.id),
                ("server_id", "=", server.id),
                ("server_dir", "=", server_dir or self.server_dir),
                ("source", "=", self.source),
            ],
            limit=1,
        )
        if existing_file:
            if raise_if_exists:
                raise ValidationError(_("File already exists on server."))
            return existing_file

        # TODO:
        return file_model.with_context(is_custom_server_dir=True).create(
            {
                "template_id": self.id,
                "server_id": server.id,
                "name": self.file_name,
                "code_on_server": self.code,
                "server_dir": server_dir or self.server_dir,
                "file_type": self.file_type,
                "source": self.source,
            }
        )
