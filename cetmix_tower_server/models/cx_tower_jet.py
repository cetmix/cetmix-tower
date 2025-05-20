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

    # Action to trigger
    action_to_trigger_id = fields.Many2one(
        comodel_name="cx.tower.jet.action",
        string="Action to Trigger",
        store=False,
        readonly=False,
        domain="[('id', 'in', available_action_ids)]",
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
                jet.trigger_action(jet.action_to_trigger_id)

    def _get_system_variable_value(self, variable_reference):
        """Return the jet template variable values

        Args:
            variable_reference (Char): variable value

        Returns:
            dict(): populates `tower` variable with with values.
                {
                    'jet_template': {..jet template vals..},
                }.
        """

        # This works for a single record only!
        self.ensure_one()

        variable_value = {}
        if variable_reference == "tower":
            variable_value.update(
                {
                    "jet": {
                        "name": self.name,  # pylint: disable=no-member
                        "reference": self.reference,  # pylint: disable=no-member
                        "state": self.state_id.name,
                    },
                }
            )
        return variable_value

    def trigger_action(self, action):
        """Trigger an action on this jet

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
                    jet=self.name,
                    state=self.state_id.name,
                )
            )

        # Execute the flight plan if defined
        if action.plan_id:
            # TODO: Implement flight plan execution for jets
            pass

        # Update the jet state
        target_state = action.state_to_id
        transit_state = action.state_transit_id
        if target_state:
            self.state_id = transit_state
            self.state_id = target_state

        # # Update the last run time
        # self.last_run_datetime = fields.Datetime.now()

        # # Log the action
        # self.env["cx.tower.jet.log"].create(
        #     {
        #         "jet_id": self.id,
        #         "action_id": action.id,
        #         "state_from_id": action.state_from_id.id,
        #         "state_to_id": target_state.id,
        #         "execution_datetime": self.last_run_datetime,
        #     }
        # )

        # return True
