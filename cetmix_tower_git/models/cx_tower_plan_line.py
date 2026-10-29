# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CxTowerPlanLine(models.Model):
    """Flight Plan Line"""

    _inherit = "cx.tower.plan.line"

    git_project_id = fields.Many2one(
        comodel_name="cx.tower.git.project",
        string="Git Project",
        help="Legacy: Git Project linked to the file created by this"
        " flight plan line. Kept for servers that do not use Jets."
        " New setups should link the Git Project to the Jet and write"
        " it with Upload Git Project. The __git_project__ custom value"
        " is also legacy.",
        yaml_export="include",
    )
    is_make_copy = fields.Boolean(
        string="Make a Copy",
        help="Legacy: create a copy of the Git Project instead of"
        " linking the file to the existing one. Never touches a Jet's"
        " Git Project.",
        yaml_export=True,
    )
