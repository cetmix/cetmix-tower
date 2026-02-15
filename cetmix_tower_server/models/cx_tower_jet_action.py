# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models
from odoo.exceptions import ValidationError


class CxTowerJetAction(models.Model):
    """Jet Actions represent transitions between states in a jet's lifecycle"""

    _name = "cx.tower.jet.action"
    _description = "Cetmix Tower Jet Action"
    _inherit = ["cx.tower.reference.mixin", "cx.tower.access.mixin"]
    _order = "priority, id"

    active = fields.Boolean(related="jet_template_id.active", readonly=True)
    priority = fields.Integer(default=10, required=True)
    jet_template_id = fields.Many2one(
        comodel_name="cx.tower.jet.template",
        string="Jet Template",
        help="Jet template that this action belongs to",
        ondelete="cascade",
    )
    color = fields.Integer(related="state_to_id.color", readonly=True)
    note = fields.Text()

    # -- State Transitions
    state_from_id = fields.Many2one(
        comodel_name="cx.tower.jet.state",
        string="From State",
        help="Source state for this transition. Leave blank for an initial state",
        ondelete="restrict",
    )

    state_transit_id = fields.Many2one(
        comodel_name="cx.tower.jet.state",
        string="Transit State",
        required=True,
        help="Intermediate state during the transition",
        ondelete="restrict",
    )

    state_to_id = fields.Many2one(
        comodel_name="cx.tower.jet.state",
        string="To State",
        help="Destination state for this transition. Leave blank for a final state",
        ondelete="restrict",
    )

    state_error_id = fields.Many2one(
        comodel_name="cx.tower.jet.state",
        string="Error State",
        help="State to transition to if an error occurs",
        ondelete="restrict",
    )

    plan_id = fields.Many2one(
        string="Flight Plan",
        comodel_name="cx.tower.plan",
        help="Flight plan to execute when this action is triggered",
    )

    # TODO: ensure that all actions belong to the same jet template

    def trigger(self, jet=None):
        """Trigger jet action on a given jet.
        If jet is not provided, the action will be triggered on the jet
        in the context key "jet_id".

        Args:
            jet (cx.tower.jet): Jet to trigger the action.
        """
        self.ensure_one()

        # Try to obtain jet from context if not provided as an argument
        if jet is None:
            jet_id = self.env.context.get("jet_id")

            # Just return, no exceptions for now
            if not jet_id:
                return

            jet = self.env["cx.tower.jet"].browse(jet_id)

        # Ensure that the action is for a single jet
        if not jet or len(jet) > 1:
            raise ValidationError(_("Action can be triggered only for a single jet"))

        # Trigger the action
        jet._trigger_action(self)

    # ------------------------------
    # Reference mixin methods
    # ------------------------------
    def _get_pre_populated_model_data(self):
        res = super()._get_pre_populated_model_data()
        res.update(
            {"cx.tower.jet.action": ["cx.tower.jet.template", "jet_template_id"]}
        )
        return res
