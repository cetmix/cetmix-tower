# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class CxTowerJetCloneWizard(models.TransientModel):
    """Clone jet"""

    _name = "cx.tower.jet.clone.wizard"
    _description = "Clone jet"

    jet_id = fields.Many2one(
        "cx.tower.jet",
        required=True,
        readonly=True,
    )
    jet_template_id = fields.Many2one(
        "cx.tower.jet.template",
        related="jet_id.jet_template_id",
        readonly=True,
    )
    same_server = fields.Selection(
        selection=[("y", "Yes"), ("n", "No")],
        default="y",
        required=True,
    )
    server_id = fields.Many2one(
        "cx.tower.server",
        domain="[('jet_template_ids', 'in', jet_template_id)]",
    )
    partner_id = fields.Many2one(
        "res.partner",
        compute="_compute_partner_id",
        store=True,
        readonly=False,
        help="Partner associated with the cloned jet",
    )
    name = fields.Char(help="The name of the new jet")
    name_type = fields.Selection(
        selection=[("a", "will be auto-generated"), ("m", "I will put myself")],
        default="a",
        required=True,
    )
    url = fields.Char(help="The URL of the jet")
    url_type = fields.Selection(
        selection=[("a", "will be auto-generated"), ("m", "I will put myself")],
        default="a",
        required=True,
    )
    state_id = fields.Many2one(
        "cx.tower.jet.state", required=True, help="Requested state of the jet"
    )
    state_domain = fields.Binary(compute="_compute_state_domain")
    use_custom_variables = fields.Selection(
        selection=[("n", "default settings"), ("y", "custom settings")],
        default="n",
        required=True,
    )
    line_ids = fields.One2many(
        "cx.tower.jet.clone.wizard.variable.line",
        "wizard_id",
        string="Variable Lines",
    )

    @api.depends("jet_id")
    def _compute_partner_id(self):
        """
        Compute the partner associated with the cloned jet
        """
        for wizard in self:
            if wizard.partner_id:
                continue
            if wizard.jet_id and wizard.jet_id.partner_id:
                wizard.partner_id = wizard.jet_id.partner_id.id

    @api.depends("jet_template_id")
    def _compute_state_domain(self):
        """
        Compute the domain for the states
        """
        for wizard in self:
            if not wizard.jet_id:
                wizard.state_domain = []
                continue
            wizard.state_domain = [
                ("id", "in", wizard.jet_template_id.action_ids.state_to_id.ids)
            ]

    def action_confirm(self):
        """
        Clone the jet
        """
        self.ensure_one()
        kwargs = {}

        # Add custom variables
        custom_variables = {}
        if self.line_ids:
            custom_variables = {
                line.variable_id.reference: line.value_char for line in self.line_ids
            }
        if custom_variables:
            kwargs["variable_values"] = custom_variables

        # Add partner
        if self.partner_id:
            kwargs["partner_id"] = self.partner_id.id

        # Add url
        if self.url_type == "m" and self.url:
            kwargs["url"] = self.url

        jet = self.jet_id.clone(
            server=self.server_id,
            name=self.name,
            state=self.state_id,
            **kwargs,
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "cx.tower.jet",
            "res_id": jet.id,
            "view_mode": "form",
            "target": "current",
        }


class CxTowerJetCloneWizardVariableLine(models.TransientModel):
    """Custom variable values for jet create wizard"""

    _name = "cx.tower.jet.clone.wizard.variable.line"
    _inherit = "cx.tower.custom.variable.value.mixin"
    _description = "Variable lines"

    wizard_id = fields.Many2one("cx.tower.jet.clone.wizard")
    # Override from mixin to make variable_id editable
    variable_id = fields.Many2one(
        readonly=False,
    )
