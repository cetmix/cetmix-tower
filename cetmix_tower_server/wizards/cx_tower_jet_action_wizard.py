# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class CxTowerJetActionWizard(models.TransientModel):
    """
    Wizard to trigger jet actions.
    """

    _name = "cx.tower.jet.action.wizard"
    _description = "Trigger Jet Action Wizard"

    action_id = fields.Many2one(
        comodel_name="cx.tower.jet.action",
        required=True,
        domain="[('id', 'in', action_available_ids)]",
    )

    jet_ids = fields.Many2many(
        comodel_name="cx.tower.jet",
        readonly=True,
    )

    action_available_ids = fields.Many2many(
        comodel_name="cx.tower.jet.action",
        compute="_compute_available_actions",
        help="Actions that are available for all selected jets",
    )

    @api.depends("jet_ids")
    def _compute_available_actions(self):
        """Compute available actions based on selected jets"""
        for wizard in self:
            if not wizard.jet_ids:
                wizard.action_available_ids = False
                continue

            # Get actions that are available to ALL selected jets
            # Start with the first jet's available actions
            first_jet = wizard.jet_ids[0]
            available_actions = first_jet.action_available_ids

            # Intersect with actions available to all other jets
            for jet in wizard.jet_ids[1:]:
                available_actions &= jet.action_available_ids

            wizard.action_available_ids = available_actions

    def action_confirm(self):
        """Trigger the action for the selected jets"""
        for wizard in self:
            if wizard.jet_ids and wizard.action_id:
                for jet in wizard.jet_ids:
                    jet._trigger_action(wizard.action_id)
        return {
            "type": "ir.actions.act_window_close",
        }
