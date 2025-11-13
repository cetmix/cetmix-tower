# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class CxTowerJetCreateWizard(models.TransientModel):
    """Create new server from template"""

    _name = "cx.tower.jet.create.wizard"
    _description = "Create new jet"

    name = fields.Char(help="The name of the jet")
    name_type = fields.Selection(
        selection=[("m", "I will put myself"), ("a", "will be auto-generated")],
        required=True,
    )
    jet_template_id = fields.Many2one(
        "cx.tower.jet.template",
        required=True,
        domain="[('show_in_wizard', '=', True)]",
    )
    server_id = fields.Many2one(
        "cx.tower.server",
        domain="[('jet_template_ids', 'in', jet_template_id)]",
    )
    state_id = fields.Many2one("cx.tower.jet.state", help="Requested state of the jet")
    state_domain = fields.Binary(compute="_compute_state_domain")
    use_custom_variables = fields.Selection(
        selection=[("n", "default settings"), ("y", "custom settings")],
        default="n",
        required=True,
    )
    line_ids = fields.One2many(
        "cx.tower.jet.create.wizard.variable.line",
        "wizard_id",
        string="Variable Lines",
    )

    @api.depends("jet_template_id")
    def _compute_state_domain(self):
        for wizard in self:
            if not wizard.jet_template_id:
                wizard.state_domain = []
                continue
            wizard.state_domain = [
                ("id", "in", wizard.jet_template_id.action_ids.state_to_id.ids)
            ]

    def action_confirm(self):
        self.ensure_one()
        custom_variables = {}
        if self.line_ids:
            custom_variables = {
                line.variable_id.reference: line.value_char for line in self.line_ids
            }
        jet = self.jet_template_id.create_jet(
            self.server_id,
            name=self.name,
            **{"configuration_variables": custom_variables},
        )
        if self.state_id:
            jet._bring_to_state(self.state_id)

        return {
            "type": "ir.actions.act_window",
            "res_model": "cx.tower.jet",
            "res_id": jet.id,
            "view_mode": "form",
            "target": "current",
        }


class CxTowerJetCreateWizardVariableLine(models.TransientModel):
    """Custom variable values for jet create wizard"""

    _name = "cx.tower.jet.create.wizard.variable.line"
    _inherit = "cx.tower.custom.variable.value.mixin"
    _description = "Variable lines"

    wizard_id = fields.Many2one("cx.tower.jet.create.wizard")
    # Override from mixin to make variable_id editable
    variable_id = fields.Many2one(
        readonly=False,
    )
