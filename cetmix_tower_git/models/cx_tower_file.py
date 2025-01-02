# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CxTowerFile(models.Model):
    _inherit = "cx.tower.file"

    git_project_ids = fields.Many2many(
        comodel_name="cx.tower.git.project",
        relation="cx_tower_git_project_rel",
        column1="file_id",
        column2="git_project_id",
        string="Git Projects",
        copy=False,
    )
    git_project_id = fields.Many2one(
        comodel_name="cx.tower.git.project",
        compute="_compute_git_project_id",
    )

    @api.depends("git_project_ids")
    def _compute_git_project_id(self):
        """
        Link to project using the proxy model.
        """
        for record in self:
            # File is related to project via proxy model.
            # So there can be only one record in o2m field.
            record.git_project_id = (
                record.git_project_ids and record.git_project_ids[0].id
            )

    @api.constrains("git_project_id")
    def _check_git_project_id(self):
        """
        Check if file is related to a single project only.
        """
        for record in self:
            if len(record.git_project_ids) > 1:
                raise ValidationError(
                    _(
                        "File '%(file)s' is related to multiple projects:"
                        " %(projects)s \n"
                        "Please select only one project.",
                        file=record.name,
                        projects=", ".join(record.git_project_ids.mapped("name")),
                    )
                )
