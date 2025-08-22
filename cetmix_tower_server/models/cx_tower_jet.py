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

    # Servers where this jet template is installed
    server_allowed_ids = fields.Many2many(
        comodel_name="cx.tower.server",
        related="jet_template_id.server_ids",
        readonly=True,
    )

    server_id = fields.Many2one(
        comodel_name="cx.tower.server",
        required=True,
        ondelete="restrict",
        domain="[('id', 'in', server_allowed_ids)]",
    )

    # --States
    state_id = fields.Many2one(
        comodel_name="cx.tower.jet.state",
        string="Current State",
        tracking=True,
    )
    state_to_id = fields.Many2one(
        comodel_name="cx.tower.jet.state",
        string="Target State",
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

        The function flow is:

        1. Bring the jet into the transit state.
        2. Execute the flight plan if defined.
        3. Bring the jet into the target state.

        Args:
            action (cx.tower.jet.action()): The action to trigger

        Returns:
            The jet is brought into the target state.
            In case of an error, the jet is brought into the error state
            if the latter is defined.

        Raises:
            ValidationError: If the action is not available for this jet.
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

        # WARNING: Explicit commit!
        # This commit is made **only** when to ensure that the state is set
        # even if the next action fails.
        # Reason: Without this commit, the change would not be visible to other
        # transactions until the end of the transaction, leading to a race
        # condition and possible double execution.
        # Explicit commits are strongly discouraged in Odoo business logic and
        # should be used only with clear justification and in strictly controlled
        # contexts (like this cron scenario). Never add this commit for general
        # business flows!
        self.env.cr.commit()  # pylint: disable=invalid-commit

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

        # Set the state to the destination state if no plan is defined
        final_vals = {
            "state_id": target_state,
            "current_action_id": False,
        }

        # Reset the target state if the jet has reached the target state
        if target_state == self.state_to_id:
            final_vals["state_to_id"] = None

        self.write(final_vals)

        # Continue the chain of actions if the final state is not reached yet
        if self.state_to_id:
            self._bring_to_state(self.state_to_id)

    def _bring_to_state(self, state=None):
        """
        Bring the jet to a specific state.

        The function flow is:

        1. Compute the path of actions to bring the jet
            to the target state.
        2. Set the target state.
        3. Trigger the first action in the path.
            This will trigger a chain of actions until the jet is brought
            into the target state.

        Args:
            state (cx.tower.jet.state()): The state to bring the jet to

        Returns:
            The jet is brought into the first state of the path.
            In case of an error, the jet is brought into the error state
            if the latter is defined.

        Raises:
            ValidationError: If the state is not defined.
            ValidationError: If the path is not found.
        """
        self.ensure_one()

        # Exit if jet is already in the target state
        if self.state_id == state:
            return

        # Compute the path of actions to bring the jet to the target state
        path = self.jet_template_id._get_action_path(
            state_from=self.state_id, state_to=state
        )
        if not path:
            raise ValidationError(
                _(
                    "No path found to bring the jet %(jet)s to the state '%(state)s'",
                    jet=self.name,  # pylint: disable=no-member
                    state=state.name,  # type: ignore
                )
            )

        # Set the target state if not already set
        if not self.state_to_id:
            self.write(
                {
                    "state_to_id": state,
                }
            )

        # Trigger the first action in the path
        self._trigger_action(path[0])

    def _flight_plan_finished(self, plan_status):
        """
        Handle the completion of a flight plan.

        Args:
            plan_status (int): The status of the flight plan
            (0: success, other: failure)
        """
        self.ensure_one()

        # Reset the current action
        vals = {"current_action_id": False}

        # If the flight plan is finished successfully,
        # we bring the jet to the destination state
        # of the current action
        if plan_status == 0:
            # Set the state to the destination state
            vals["state_id"] = (
                self.current_action_id.state_to_id
                and self.current_action_id.state_to_id.id
            )

            # Reset the target state if the jet has reached the target state
            # This will stop the chain of actions
            if self.state_to_id == self.state_id:
                vals["state_to_id"] = None

        # If the flight plan is finished with an error,
        # we bring the jet to the error state if it is defined
        # or back to the initial state if not
        # Reset the target state because we cannot continue the chain of actions
        else:
            vals.update(
                {
                    "state_id": (
                        self.current_action_id.state_error_id
                        and self.current_action_id.state_error_id.id
                    )
                    or (
                        self.current_action_id.state_from_id
                        and self.current_action_id.state_from_id.id
                    ),
                    "state_to_id": None,
                }
            )

        self.write(vals)

        # Continue the chain of actions if the final state is not reached yet
        if self.state_to_id:
            self._bring_to_state(self.state_to_id)
