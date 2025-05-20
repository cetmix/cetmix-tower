# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class CxTowerJetStateWizard(models.TransientModel):
    """
    Wizard to set state for selected jets.
    """

    _name = "cx.tower.jet.state.wizard"
    _description = "Set Jet State Wizard"

    jet_ids = fields.Many2many(
        comodel_name="cx.tower.jet",
        string="Jets",
        required=True,
        readonly=True,
    )

    state_id = fields.Many2one(
        comodel_name="cx.tower.jet.state",
        required=True,
        domain="[('id', 'in', available_state_ids)]",
    )

    available_state_ids = fields.Many2many(
        comodel_name="cx.tower.jet.state",
        string="Available States",
        compute="_compute_available_states",
        help="States that appear in the 'state_to' field "
        "of jet templates of all selected jets",
    )

    @api.depends("jet_ids", "jet_ids.jet_template_id.action_ids.state_to_id")
    def _compute_available_states(self):
        """Compute available states based on selected jets' templates"""

        # Used as a placeholder for no available states
        state_obj = self.env["cx.tower.jet.state"]

        for wizard in self:
            if not wizard.jet_ids:
                wizard.available_state_ids = False
                continue

            # Get states that are available to ALL selected jets
            # Start with the first jet's available states
            first_jet = wizard.jet_ids[0]
            if not first_jet.jet_template_id.action_ids:
                wizard.available_state_ids = False
                continue

            available_states = first_jet.jet_template_id.action_ids.mapped(
                "state_to_id"
            )

            # Intersect with states available to all other jets
            for jet in wizard.jet_ids[1:]:
                actions = jet.jet_template_id.action_ids
                # If no actions, no available states
                if not actions:
                    available_states = state_obj
                    break
                jet_states = actions.mapped("state_to_id")
                available_states &= jet_states

            # Remove current state from available states if only one jet is selected
            if len(wizard.jet_ids) == 1:
                available_states -= wizard.jet_ids.state_id
            wizard.available_state_ids = available_states

    def action_confirm(self):
        """Bring the jets to the target state"""
        for wizard in self:
            if wizard.jet_ids and wizard.state_id:
                for jet in wizard.jet_ids:
                    jet.bring_to_state(wizard.state_id.reference)
