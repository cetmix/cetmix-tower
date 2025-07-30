# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CxTowerPlanLine(models.Model):
    """Flight Plan Line"""

    _inherit = "cx.tower.plan.line"

    git_project_id = fields.Many2one(
        comodel_name="cx.tower.git.project",
        string="Git Project",
        help="Select a git project to be linked to the file and server.",
    )
    is_make_copy = fields.Boolean(
        string="Make a Copy",
        help="Create a copy of the Git Project instead of linking "
        "the file to the existing one.",
    )

    # ------------------------------
    # YAML mixin methods
    # ------------------------------
    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "git_project_id",
            "is_make_copy",
        ]
        return res
