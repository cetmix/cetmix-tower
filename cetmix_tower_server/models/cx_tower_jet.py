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

    jet_template_id = fields.Many2one(
        comodel_name="cx.tower.jet.template",
        required=True,
        ondelete="restrict",
        help="Template that this jet is based on",
    )
    jet_request_id = fields.Many2one(
        comodel_name="cx.tower.jet.request",
        help="Request this jet is currently processing",
    )
    server_allowed_ids = fields.Many2many(
        comodel_name="cx.tower.server",
        related="jet_template_id.server_ids",
        readonly=True,
        help="Servers where this jet template is installed",
    )
    server_id = fields.Many2one(
        comodel_name="cx.tower.server",
        required=True,
        ondelete="restrict",
        domain="[('id', 'in', server_allowed_ids)]",
        help="Server where this jet is running",
    )
    jet_linked_to_ids = fields.Many2many(
        comodel_name="cx.tower.jet",
        relation="cx_tower_jet_jet_linked_rel",
        column1="jet_id",
        column2="jet_linked_to_id",
        string="Linked to",
        help="Jets this jet is linked to",
        copy=False,
    )
    jet_linked_from_ids = fields.Many2many(
        comodel_name="cx.tower.jet",
        relation="cx_tower_jet_jet_linked_rel",
        column1="jet_linked_to_id",
        column2="jet_id",
        string="Linked from",
        help="Jets that are linked to this jet",
        copy=False,
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
        help="Destination state to which the jet is currently transitioning",
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

    def create(self, vals_list):
        """Create new jets and handle the entry into the initial state"""
        jets = super().create(vals_list)
        for jet in jets:
            jet._on_state_enter(state=jet.state_id)
        return jets

    def write(self, vals):
        """Handle the entry into the new state"""
        if "state_id" in vals:
            for jet in self:
                jet._on_state_exit(state=jet.state_id)
            res = super().write(vals)
            for jet in self:
                jet._on_state_enter(state=jet.state_id)
        else:
            res = super().write(vals)
        return res

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   Odoo Actions
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
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

    def action_open_state_wizard(self):
        """Open the jet state wizard"""
        self.ensure_one()

        context = self.env.context.copy()
        context["default_jet_ids"] = [(6, 0, self.ids)]
        action = {
            "type": "ir.actions.act_window",
            "res_model": "cx.tower.jet.state.wizard",
            "view_mode": "form",
            "target": "new",
            "context": context,
        }
        return action

    def action_open_action_wizard(self):
        """Open the jet action wizard"""
        self.ensure_one()
        context = self.env.context.copy()
        context["default_jet_ids"] = [(6, 0, self.ids)]
        action = {
            "type": "ir.actions.act_window",
            "res_model": "cx.tower.jet.action.wizard",
            "view_mode": "form",
            "target": "new",
            "context": context,
        }
        return action

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   Trigger Actions and change states
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

        # Trigger the transition finished event
        self._finalize_transition(failed=False)

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

        # Used in case this is the last action in the chain
        transition_failed = False

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
            transition_failed = True

        self.write(vals)

        # Continue the chain of actions if the final state is not reached yet
        if self.state_to_id:
            self._bring_to_state(self.state_to_id)

        # Trigger the transition finished event
        self._finalize_transition(failed=transition_failed)

    def _finalize_transition(self, failed=False):
        """
        Handle the completion of a state transition.

        Args:
            failed (bool): True if the transition failed, False otherwise
        """
        self.ensure_one()

        # 1. Finalize the jet request if it exists
        if self.jet_request_id:
            self.jet_request_id._finalize(result="success" if not failed else "failed")

        # 2. Notify the jet that it is available
        self._on_is_available()

    def _finalize_request(self, result="success"):
        """
        Finalize the jet request.
        """
        self.ensure_one()

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   Events handling
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def _on_state_exit(self, state=None):
        """
        Handle the exit of the jet from a state.

        Args:
            state (cx.tower.jet.state()): The state jet is exiting
        """
        self.ensure_one()
        # TODO: Implement the logic to handle the exit of the jet from a state
        pass

    def _on_state_enter(self, state=None):
        """
        Handle the entry of the jet into a state.

        Args:
            state (cx.tower.jet.state()): The state jet is entering
        """
        self.ensure_one()
        # TODO: Implement the logic to handle the entry of the jet into a state
        pass

    def _on_is_available(self):
        """
        Handle the event when the jet is not busy anymore.
        """

        # Process pending requests
        jet_request_obj = self.env["cx.tower.jet.request"]

        # 1. Requests where the jet is requested explicitly
        explicit_requests = jet_request_obj.search(
            [
                ("jet_id", "=", self.id),  # pylint: disable=no-member
                ("state", "=", "new"),
            ]
        )
        if explicit_requests:
            # Check which state is required by the request
            # TODO: IMPORTANT: we must find a workaround to avoid infinite loops
            # when different jets keep requesting the same target jet in different
            # states and the target jet keeps jumping from one state to another.

            # Finalize all requests that request the same state as the jet
            same_state_requests = explicit_requests.filtered(
                lambda r: r.state_requested_id == self.state_id
            )
            for request in same_state_requests:
                request._finalize(result="success")

            # Pick the first request that requests a different state
            remaining_requests = explicit_requests - same_state_requests
            if remaining_requests:
                self._bring_to_state(remaining_requests[0].state_requested_id)

        # 2. Requests where the jet is requested implicitly via template
        if self._accepts_new_links():
            implicit_requests = jet_request_obj.search(
                [
                    ("server_id", "=", self.server_id),
                    ("jet_template_id", "=", self.jet_template_id),
                    ("state", "=", "new"),
                ]
            )
            same_state_requests = implicit_requests.filtered(
                lambda r: r.state_requested_id == self.state_id
            )
            if same_state_requests:
                # Set current jet as the target jet for the requests
                same_state_requests.write({"jet_id": self.id})  # pylint: disable=no-member
                for request in same_state_requests:
                    request._finalize(result="success")

            # Pick the first request that requests a different state
            remaining_requests = implicit_requests - same_state_requests
            if remaining_requests:
                remaining_request = remaining_requests[0]
                # Set current jet as the target jet for the request
                remaining_request.write({"jet_id": self.id})  # pylint: disable=no-member
                self._bring_to_state(remaining_request.state_requested_id)

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   Status and busyness
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def _accepts_new_links(self):
        """
        Check if the jet is available to accept new links from other jets.

        Returns:
            bool: True if the jet is available to accept new links from other jets,
                False otherwise
        """
        self.ensure_one()
        # TODO: Implement the logic to check if the jet is available
        # to accept new links from other jets
        return True

    def _is_busy(self):
        """
        Check if the jet is busy with some other action.
        Overwrite this function to implement custom logic.

        Returns:
            bool: True if the jet is busy with some other action,
                False otherwise
        """
        self.ensure_one()

        # Jet is considered busy if it is currently transitioning to another state
        busy = bool(self.state_to_id)
        return busy

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   Manage dependencies
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def _provide_dependencies(self):
        """
        Provide dependencies to the jet.
        Ensure that the jets this jet depends exist
        and are in the correct state.
        """
        self.ensure_one()

        # Get the dependencies of the jet from the template
        dependencies = self.jet_template_id.template_requires_ids
        jet_request_obj = self.env["cx.tower.jet.request"]
        for dependency in dependencies:
            jet_request_obj._create_request(
                server=self.server_id,
                jet_template=dependency.template_required_id,
                state=dependency.state_required_id,
                requested_by_jet=self,
            )

    def _check_dependencies(self):
        """
        Check if the jet has any dependencies.
        """
        self.ensure_one()
        # TODO: Implement the logic to check if the jet has any dependencies
        pass
