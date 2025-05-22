# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class CxTowerJetTemplate(models.Model):
    """Jet Templates are templates to create and manage jets"""

    _name = "cx.tower.jet.template"
    _description = "Cetmix Tower Jet Template"
    _inherit = [
        "cx.tower.reference.mixin",
        "cx.tower.access.mixin",
        "cx.tower.variable.mixin",
    ]

    active = fields.Boolean(default=True)
    tag_ids = fields.Many2many(
        comodel_name="cx.tower.tag",
        relation="cx_tower_jet_template_tag_rel",
        column1="jet_template_id",
        column2="tag_id",
        string="Tags",
    )
    note = fields.Text()

    server_ids = fields.Many2many(
        comodel_name="cx.tower.server",
        relation="cx_tower_jet_template_server_rel",
        column1="jet_template_id",
        column2="server_id",
        string="Installed on Servers",
        readonly=False,
        help="These servers have this jet template installed",
    )

    # Flight Plan
    plan_install_id = fields.Many2one(
        comodel_name="cx.tower.plan",
        string="Flight Plan for Installation",
        help="Flight plan used to install the template from a server",
    )
    plan_uninstall_id = fields.Many2one(
        comodel_name="cx.tower.plan",
        string="Flight Plan for Uninstallation",
        help="Flight plan used to uninstall the template from a server",
    )

    # Configuration variables
    variable_value_ids = fields.One2many(
        inverse_name="jet_template_id",
    )

    # Actions
    action_ids = fields.One2many(
        comodel_name="cx.tower.jet.action",
        inverse_name="jet_template_id",
        string="Lifecycle Actions",
    )

    # Dependencies
    template_requires_ids = fields.One2many(
        comodel_name="cx.tower.jet.dependency",
        inverse_name="template_id",
        string="Requires",
        help="Define other templates that must be in specific"
        " states for this template to function",
    )
    template_required_by_ids = fields.One2many(
        comodel_name="cx.tower.jet.dependency",
        inverse_name="template_required_id",
        string="Required by",
        help="Define other templates that require this template to be in a specific"
        " state to function",
    )

    # Messages
    message_actions = fields.Text(compute="_compute_message_actions")

    @api.depends(
        "action_ids.state_from_id",
        "action_ids.state_to_id",
        "action_ids.name",
        "action_ids.priority",
    )
    def _compute_message_actions(self):
        """Compute the warning message for the actions."""
        for template in self:
            template.message_actions = template._compose_message_actions()

    def action_install_on_servers(self):
        """Action to install the Jet Template on the selected servers."""
        self.ensure_one()
        # Open the wizard to install the template on the selected servers
        return {
            "type": "ir.actions.act_window",
            "name": "Install on Servers",
            "res_model": "cx.tower.jet.template.install.wiz",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_jet_template_id": self.id,
            },
        }

    def _compose_message_actions(self):
        """Compose the warning message for the actions."""
        self.ensure_one()
        message = ""

        # Find actions without states
        initial_actions = final_actions = self.env["cx.tower.jet.action"]
        for action in self.action_ids:
            if not action.state_from_id and action.state_to_id:
                initial_actions |= action
            if not action.state_to_id and action.state_from_id:
                final_actions |= action

        # Parse the initial actions
        if not initial_actions:
            message = _(
                "You need to define at least one initial action "
                "with the empty 'From State'."
            )
        else:
            # Get the name of the first initial action (which will be used as default)
            default_action = initial_actions[0]
            message = _(
                "Default initial action is '%(action_name)s'.",
                action_name=default_action.name,
            )

            # If there are multiple initial actions, add an additional message
            if len(initial_actions) > 1:
                message += _(
                    "The first action with an empty 'From State' "
                    "is used as the initial action."
                )

        # Parse the final actions
        if not final_actions:
            message += "\n" + _(
                "You need to define at least one final action "
                "with the empty 'To State'."
            )
        else:
            # Get the name of the first initial action (which will be used as default)
            default_action = final_actions[0]
            message += "\n" + _(
                "Default final action is '%(action_name)s'.",
                action_name=default_action.name,
            )

            # If there are multiple initial actions, add an additional message
            if len(final_actions) > 1:
                message += _(
                    "The first action with an empty 'To State' "
                    "is used as the final action."
                )
        return message

    def install_on_servers(self, servers):
        """Install the Jet Template on the selected servers.

        Args:
            servers (cx.tower.server()): Servers to install the Jet Template on
        """
        self.ensure_one()

        # Save the action being performed on the Jet Template
        kwargs = {
            "plan_log": {
                "jet_template_action": "i",
            },
        }
        for server in servers:
            if self.plan_install_id:
                server.run_flight_plan(
                    self.plan_install_id, jet_template=self, **kwargs
                )
            else:
                self._finish_install(server)

    def _finish_install(self, server, success=True):
        """Finish the installation of the Jet Template on the server.
        This method is called when the installation plan finishes.

        Args:
            server (cx.tower.server()): Server to finish the installation on
            success (bool): True if the installation was successful, False otherwise
        """
        self.ensure_one()
        if success:
            self.write({"server_ids": [(4, server.id)]})

        # Call the post-install hook
        self._post_finish_install(server, success)
        return

    def _post_finish_install(self, server, success):
        """Helper method to implement post-install actions.

        Args:
            server (cx.tower.server()): Server to finish the uninstallation on
            status (str): Status of the uninstallation. Possible values:
                - "success": Uninstallation was successful
        """
        return

    def uninstall_from_servers(self, servers):
        """Uninstall the Jet Template from the selected servers.

        Args:
            servers (cx.tower.server()): Servers to uninstall the Jet Template from
        """
        self.ensure_one()
        # TODO: Implement the uninstallation
        pass

    # def _get_action_path(self, state_from=None, state_to=None):
    #     """Get the sequence of actions needed to transition
    #     from one state to another

    #     Args:
    #         state_from (cx.tower.jet.state): The initial state
    #         state_to (cx.tower.jet.state): The target state

    #     Returns:
    #         List of actions that need to be executed in sequence
    #         to reach the target state
    #     """
    #     if not state_to:
    #         return []

    #     # Direct path - if there's a direct action from source to target
    #     direct_actions = self.action_ids.filtered(
    #         lambda a: a.state_from_id == state_from and a.state_to_id == state_to
    #     )
    #     if direct_actions:
    #         return direct_actions[0]

    #     # If state_from is not provided, look for initial actions
    #     if not state_from:
    #         initial_actions = self.action_ids.filtered(
    #             lambda a: not a.state_from_id and a.state_to_id
    #         )
    #         if initial_actions:
    #             return initial_actions[0]
    #         return []

    #     # Build a graph representation of states and transitions
    #     graph = {}
    #     for action in self.action_ids:
    #         # Skip actions that have both states empty
    #         if not action.state_from_id and not action.state_to_id:
    #             continue

    #         # Handle initial actions (empty state_from)
    #         if not action.state_from_id:
    #             if "initial" not in graph:
    #                 graph["initial"] = {}
    #             graph["initial"][action.state_to_id.id] = action
    #             continue

    #         # Handle regular actions
    #         if action.state_to_id:  # Only process if to_state is set
    #             from_id = action.state_from_id.id
    #             to_id = action.state_to_id.id

    #             if from_id not in graph:
    #                 graph[from_id] = {}

    #             # Store the action ID that connects these states
    #             graph[from_id][to_id] = action

    #     # BFS to find shortest path
    #     start_node = state_from.id
    #     queue = [(start_node, [])]  # (current_state, path_so_far)
    #     visited = set()

    #     # Also try paths starting with initial actions if available
    #     if "initial" in graph:
    #         for to_state, action in graph["initial"].items():
    #             queue.append((to_state, [action]))

    #     while queue:
    #         current, path = queue.pop(0)

    #         if current == state_to.id:
    #             return path  # Found the path to target state

    #         if current in visited:
    #             continue

    #         visited.add(current)

    #         # Check all possible transitions from current state
    #         for next_state, action in graph.get(current, {}).items():
    #             if next_state not in visited:
    #                 queue.append((next_state, path + [action]))

    #     # No path found
    #     return []

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
                    "jet_template": {
                        "name": self.name,  # pylint: disable=no-member
                        "reference": self.reference,  # pylint: disable=no-member
                    },
                }
            )
        return variable_value
