# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerServer(models.Model):
    _inherit = "cx.tower.server"

    git_project_rel_ids = fields.One2many(
        comodel_name="cx.tower.git.project.rel",
        inverse_name="server_id",
        copy=False,
        depends=["git_project_ids"],
        groups="cetmix_tower_server.group_manager,cetmix_tower_server.group_root",
    )

    # Helper field to get all git projects related to server
    # IMPORTANT: This field may contain duplicates because of the relation nature!
    git_project_ids = fields.Many2many(
        comodel_name="cx.tower.git.project",
        relation="cx_tower_git_project_rel",
        column1="server_id",
        column2="git_project_id",
        readonly=True,
        copy=False,
        depends=["git_project_rel_ids"],
        groups="cetmix_tower_server.group_manager,cetmix_tower_server.group_root",
    )

    # ------------------------------
    # YAML mixin methods
    # ------------------------------
    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "git_project_rel_ids",
        ]
        return res
