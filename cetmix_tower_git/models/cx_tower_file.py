# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


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
