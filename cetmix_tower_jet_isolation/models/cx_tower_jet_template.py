# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


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
        selection=lambda self: self.env["cx.tower.plan.run.wizard"]
        ._fields["applicability"]
        .selection,
        string="Forced Applicability",
    )

    forced_command_tag_ids = fields.Many2many(
        comodel_name="cx.tower.tag",
        relation="cx_tower_jet_template_forced_command_tag_rel",
        column1="jet_template_id",
        column2="tag_id",
        string="Forced Command Tags",
    )

    forced_plan_tag_ids = fields.Many2many(
        comodel_name="cx.tower.tag",
        relation="cx_tower_jet_template_forced_plan_tag_rel",
        column1="jet_template_id",
        column2="tag_id",
        string="Forced Flight Plan Tags",
    )

    @api.onchange("isolation_mode")
    def _onchange_isolation_mode(self):
        """Clear forced values when isolation is disabled"""
        if not self.isolation_mode:
            self.forced_applicability = False
            self.forced_command_tag_ids = [(5, 0, 0)]
            self.forced_plan_tag_ids = [(5, 0, 0)]

    @api.constrains("isolation_mode", "forced_applicability")
    def _check_forced_applicability(self):
        for record in self:
            if record.isolation_mode and not record.forced_applicability:
                raise ValidationError(
                    _("Please specify Forced Applicability when Isolation Mode is active.")
                )
