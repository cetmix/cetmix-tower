# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CxTowerJetStateTransition(models.Model):
    """
    Handles transition of a jet from one state to another.
    """

    _name = "cx.tower.jet.state.transition"
    _description = "Jet State Transition"

    jet_id = fields.Many2one(
        comodel_name="cx.tower.jet",
        string="Jet",
        help="Jet that is being transitioned",
        auto_join=True,
    )

    state_from_id = fields.Many2one(
        comodel_name="cx.tower.jet.state",
        string="From State",
        help="Initial state of the jet",
    )

    state_to_id = fields.Many2one(
        comodel_name="cx.tower.jet.state",
        string="To State",
        help="Destination state of the jet",
    )

    state_id = fields.Many2one(
        comodel_name="cx.tower.jet.state",
        string="Current State",
        help="Current state of the jet",
    )

    transition_state = fields.Selection(
        selection=[
            ("processing", "Processing"),
            ("done", "Done"),
            ("failed", "Failed"),
        ],
        default="processing",
        help="Current state of the transition",
    )

    def _process(self):
        """
        Run the transition.
        """
        self.ensure_one()

        # If state is the same as the destination state,
        # set the transition state to done
        if self.state_id == self.state_to_id:
            self.write({"transition_state": "done"})
            self.jet_id.write(
                {"state_id": self.state_to_id, "current_action_id": False}
            )
            return

        # Compute the path of actions to bring the jet to the target state
        path = self.jet_id.jet_template_id._get_action_path(
            state_from=self.state_id, state_to=self.state_to_id
        )

        # Execute the actions in the path
        for action in path:
            # Set the jet state to the transit state and current action
            self.jet_id.write(
                {
                    "state_id": action.state_transit_id.id,
                    "current_action_id": action.id,
                }
            )

            # If action has a flight plan, run it
            if action.plan_id:
                self.jet_id.server_id.run_flight_plan(  # pylint: disable=no-member
                    flight_plan=action.plan_id,
                    jet=self.jet_id,
                )
                # Return, because will get a callback from the flight plan
                return

            # Otherwise update the jet state to the target state
            self.jet_id.write(
                {"state_id": self.state_to_id, "current_action_id": False}
            )

        # Set the transition state to done
        self.write({"transition_state": "done"})

    def _flight_plan_finished(self, plan_status):
        """
        Handle the completion of a flight plan.
        """
        self.ensure_one()

        # If the flight plan failed, set the transition state to failed
        if plan_status != 0:
            # Mark current transition as failed
            self.write({"transition_state": "failed"})
            # Set the jet state to the initial state and remove the current action
            self.jet_id.write(
                {"state_id": self.state_from_id, "current_action_id": False}
            )
            return

        # If the flight plan succeeded set the jet state to the target state
        self.jet_id.write({"state_id": self.state_to_id, "current_action_id": False})
