# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class CxTowerFile(models.Model):
    _inherit = "cx.tower.file"

    git_project_id = fields.Many2one(
        comodel_name="cx.tower.git.project",
        compute="_compute_git_project_id",
        store=True,
    )
    git_project_rel_ids = fields.One2many(
        comodel_name="cx.tower.git.project.rel",
        inverse_name="file_id",
        string="Git Project Relations",
        copy=False,
    )

    # Get server from the first related git project relation
    # This is needed for YAML import
    server_id = fields.Many2one(
        comodel_name="cx.tower.server",
        compute="_compute_git_project_id",
        store=True,
        readonly=False,
    )

    @api.depends("git_project_rel_ids.server_id", "git_project_rel_ids.git_project_id")
    def _compute_git_project_id(self):
        """
        Link to project using the proxy model.
        """
        for record in self:
            # File is related to project via proxy model.
            # So there can be only one record in o2m field.
            git_project_relation = (
                record.git_project_rel_ids and record.git_project_rel_ids[0]
            )
            if git_project_relation:
                record.update(
                    {
                        "git_project_id": git_project_relation.git_project_id,
                        "server_id": git_project_relation.server_id,
                    }
                )
            else:
                # Reset only git project id as file still belongs to the server
                record.update(
                    {
                        "git_project_id": False,
                    }
                )
