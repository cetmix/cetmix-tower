# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CxTowerJet(models.Model):
    """Link Jets to Odoo Project tasks."""

    _inherit = "cx.tower.jet"

    project_task_id = fields.Many2one(
        comodel_name="project.task",
        ondelete="set null",
        copy=False,
        index=True,
        help="Project task this Jet is associated with.",
    )
