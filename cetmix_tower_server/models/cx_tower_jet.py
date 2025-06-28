# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CxTowerJet(models.Model):
    """Jets represent application instances that can be managed independently"""

    _name = "cx.tower.jet"
    _description = "Cetmix Tower Jet"
    _inherit = [
        "cx.tower.reference.mixin",
        "cx.tower.variable.mixin",
        "mail.thread",
        "mail.activity.mixin",
    ]

    active = fields.Boolean(default=True)
    url = fields.Char()
    color = fields.Integer(related="state_id.color", readonly=True)

    # Template this Jet is based on
    jet_template_id = fields.Many2one(
        comodel_name="cx.tower.jet.template",
        required=True,
        ondelete="restrict",
    )

    # Server this Jet is running on
    server_ids = fields.Many2many(
        comodel_name="cx.tower.server",
        related="jet_template_id.server_ids",
        readonly=True,
    )

    server_id = fields.Many2one(
        comodel_name="cx.tower.server",
        required=True,
        ondelete="restrict",
        domain="[('id', 'in', server_ids)]",
    )

    # Current state of the Jet
    state_id = fields.Many2one(
        comodel_name="cx.tower.jet.state",
        string="Current State",
        tracking=True,
    )

    # Currently executing action
    current_action_id = fields.Many2one(
        comodel_name="cx.tower.jet.action",
        string="Currently Executing Action",
    )

    # Variables used for configuration
    variable_value_ids = fields.One2many(
        inverse_name="jet_id",
    )

    # Available actions based on current state
    available_action_ids = fields.Many2many(
        comodel_name="cx.tower.jet.action",
        compute="_compute_available_actions",
        string="Available Actions",
    )

    command_log_ids = fields.One2many(
        comodel_name="cx.tower.command.log",
        inverse_name="jet_id",
    )
    plan_log_ids = fields.One2many(
        comodel_name="cx.tower.plan.log",
        inverse_name="jet_id",
    )

    # TODO: test
    test_state_id = fields.Many2one(
        comodel_name="cx.tower.jet.state",
        string="Test State",
    )
    # TODO: test
    # Action to trigger
    action_to_trigger_id = fields.Many2one(
        comodel_name="cx.tower.jet.action",
        string="Action to Trigger",
        store=False,
        readonly=False,
        domain="[('id', 'in', available_action_ids)]",
    )

    @api.depends("state_id", "jet_template_id")
    def _compute_available_actions(self):
        """Compute available actions based on current state and template"""
        for jet in self:
            if not jet.jet_template_id:
                jet.available_action_ids = False
                continue

            # Find actions in the template that start from the current state
            actions = jet.jet_template_id.action_ids.filtered(
                lambda a, state=jet.state_id: a.state_from_id == state
            )
            jet.available_action_ids = actions

    @api.constrains("server_id", "jet_template_id")
    def _check_server_template_compatibility(self):
        """Ensure that the server is allowed to use this jet template"""
        for jet in self:
            template = jet.jet_template_id
            server = jet.server_id

            # Check if the server is directly allowed
            if server in template.server_ids:
                continue

            raise ValidationError(
                _(
                    "Server '%(server)s' is not allowed to use "
                    "jet template '%(template)s'",
                    server=server.name,
                    template=template.name,
                )
            )

    @api.onchange("action_to_trigger_id")
    def _onchange_action_to_trigger_id(self):
        """Onchange action to trigger"""
        for jet in self:
            if jet.action_to_trigger_id:
                jet._trigger_action(jet.action_to_trigger_id)

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   Odoo Actions
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def action_test(self):
        """Test the jet"""
        self.ensure_one()
        self._bring_to_state(self.test_state_id)

    def action_open_command_logs(self):
        """
        Open current server command log records
        """
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_command_log"
        )
        action["domain"] = [("jet_id", "=", self.id)]  # pylint: disable=no-member
        return action

    def action_open_plan_logs(self):
        """
        Open current server flightplan log records
        """
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_plan_log"
        )
        action["domain"] = [("jet_id", "=", self.id)]  # pylint: disable=no-member
        return action

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   Jet Actions and states
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def _trigger_action(self, action):
        """Trigger an action on the jet.

        Args:
            action (cx.tower.jet.action()): The action to trigger

        Returns:
            Result of the action execution
        """
        self.ensure_one()

        # Ensure the action is available for this jet
        if action.id not in self.available_action_ids.ids:
            raise ValidationError(
                _(
                    "Action '%(action)s' is not available for jet"
                    " '%(jet)s' in state '%(state)s'",
                    action=action.name,
                    jet=self.name,  # pylint: disable=no-member
                    state=self.state_id.name,
                )
            )

        # Update the jet state
        transit_state = action.state_transit_id
        target_state = action.state_to_id
        self.write(
            {
                "state_id": transit_state,
                "current_action_id": action.id,
            }
        )

        # Execute the flight plan if defined
        if action.plan_id:
            # Run the flight plan
            self.server_id.run_flight_plan(
                flight_plan=action.plan_id,
                jet=self,
            )
            # Flight plan will trigger the `_flight_plan_finished` function again
            # if the flight plan is finished successfully.
            # So we don't need continue the loop in this case.
            return

        self.write(
            {
                "state_id": target_state,
                "current_action_id": False,
            }
        )

    def _bring_to_state(self, state=None):
        """
        Bring the jet to a specific state.

        Args:
            state (cx.tower.jet.state()): The state to bring the jet to
        """
        self.ensure_one()

        # Exit if jet is already in the target state or running an action
        if self.state_id == state or self.current_action_id:
            return

        # Create a new state transition
        self.env["cx.tower.jet.state.transition"].create(
            {
                "jet_id": self.id,  # pylint: disable=no-member
                "state_from_id": self.state_id,
                "state_to_id": state,
                "state_id": self.state_id,
            }
        )

    def _bring_to_state_old(self, state=None):
        """
        Bring the jet to a specific state.

        Args:
            state (cx.tower.jet.state()): The state to bring the jet to

        Returns:
        """
        self.ensure_one()

        # Set the destination state
        self.write(
            {
                "state_to_id": state,
            }
        )

        # Compute the path of actions to bring the jet to the target state
        path = self.jet_template_id._get_action_path(
            state_from=self.state_id, state_to=state
        )

        # Execute the actions in the path
        for action in path:
            self._trigger_action(action)

    def _flight_plan_finished(self, plan_status):
        """
        Handle the completion of a flight plan.

        Args:
            plan_status (int): The status of the flight plan
            (0: success, other: failure)
        """
        self.ensure_one()

        vals = {"current_action_id": False}
        if plan_status == 0:
            # Set the state to the destination state
            vals["state_id"] = (
                self.current_action_id.state_to_id
                and self.current_action_id.state_to_id.id
            )  # type: ignore

            # Check if the action state is the destination state
            # If we have reached the destination state, nothing to do here anymore
            if self.current_action_id.state_to_id == self.state_to_id:
                self.write(vals)

        self.write(vals)
