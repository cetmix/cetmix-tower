# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CxTowerJetTemplate(models.Model):
    """Jet Templates are templates to create and manage jets.
    This model adds isolation settings to the jet template.
    """

    _description = "Cetmix Tower Jet Template"
    _inherit = "cx.tower.jet.template"

    isolation_mode = fields.Boolean(
        string="Isolation Mode",
        help="When active, prevents users from changing applicability or tags "
        "when running commands.",
    )
    forced_applicability = fields.Selection(
        selection=[
            ("this", "For selected server(s)"),
            ("shared", "Non server restricted"),
        ],
        string="Forced Applicability",
    )

    forced_command_tag_ids = fields.Many2many(
        comodel_name="cx.tower.tag",
        relation="cx_tower_template_forced_command_tag_rel",
        string="Forced Command Tags",
    )

    forced_plan_tag_ids = fields.Many2many(
        comodel_name="cx.tower.tag",
        relation="cx_tower_template_forced_plan_tag_rel",
        string="Forced Flight Plan Tags",
    )
