# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import ast
import logging

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .constants import (
    JET_ACTION_NOT_AVAILABLE,
    JET_DEPENDENCIES_NOT_SATISFIED,
    JET_STATE_ERROR,
)
from .tools import generate_random_id

_logger = logging.getLogger(__name__)


class CxTowerJet(models.Model):
    """Jets represent application instances that can be managed independently"""

    _name = "cx.tower.jet"
    _description = "Cetmix Tower Jet"
    _inherit = [
        "cx.tower.reference.mixin",
        "cx.tower.variable.mixin",
        "cx.tower.metadata.mixin",
        "mail.thread",
        "mail.activity.mixin",
        "cx.tower.tag.mixin",
        "cx.tower.access.role.mixin",
    ]
    _order = "sequence, name"
    _mail_post_access = "read"

    active = fields.Boolean(default=True)
    deletable = fields.Boolean(
        readonly=True,
        default=True,
        help="This field is set by the jet actions. "
        "If enabled, the jet can be deleted",
    )
    url = fields.Char(string="URL", help="Jet URL, eg 'https://meme.example.com'")
    color = fields.Integer(related="state_id.color", readonly=True)
    icon = fields.Image(
        string="Icon image",
        related="jet_template_id.icon",
        readonly=True,
        store=False,
        help="Jet icon, computed from the template by default",
    )
    sequence = fields.Integer(default=10, help="Used to sort jets in views")
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        help="Partner associated with this jet",
    )
    note = fields.Text()

    jet_cloned_from_id = fields.Many2one(
        comodel_name="cx.tower.jet",
        string="Cloned from",
        readonly=True,
        copy=False,
        help="Jet this jet was cloned from. "
        "This field is set when the jet is cloned from another jet.",
    )

    jet_template_id = fields.Many2one(
        comodel_name="cx.tower.jet.template",
        required=True,
        ondelete="restrict",
        help="Template that this jet is based on",
    )
    jet_template_domain = fields.Binary(
        compute="_compute_jet_template_domain",
    )
    server_id = fields.Many2one(
        comodel_name="cx.tower.server",
        required=True,
        ondelete="restrict",
        help="Server where this jet is running",
    )
    server_allowed_domain = fields.Binary(
        compute="_compute_server_allowed_domain",
    )
    file_ids = fields.One2many(
        comodel_name="cx.tower.file",
        inverse_name="jet_id",
        string="Files",
        help="Files of this jet",
    )
    server_log_ids = fields.One2many(
        comodel_name="cx.tower.server.log",
        inverse_name="jet_id",
        copy=False,
    )
    scheduled_task_ids = fields.Many2many(
        comodel_name="cx.tower.scheduled.task",
        relation="cx_tower_scheduled_task_jet_rel",
        column1="jet_id",
        column2="scheduled_task_id",
        string="Scheduled Tasks",
    )

    # -- Jet Requests
    served_jet_request_id = fields.Many2one(
        comodel_name="cx.tower.jet.request",
        help="Request this jet is currently serving",
        readonly=True,
        copy=False,
    )

    # -- Dependencies
    jet_requires_ids = fields.One2many(
        comodel_name="cx.tower.jet.dependency",
        inverse_name="jet_id",
        string="Requires",
        help="Other jets this jet depends on",
        compute="_compute_jet_requires_ids",
        store=True,
        groups="cetmix_tower_server.group_manager",
        copy=False,
    )
    jet_required_by_ids = fields.One2many(
        comodel_name="cx.tower.jet.dependency",
        inverse_name="jet_depends_on_id",
        string="Required By",
        help="Jets that depend on this jet",
        groups="cetmix_tower_server.group_manager",
        copy=False,
        readonly=True,
    )

    # -- States and actions
    state_id = fields.Many2one(
        comodel_name="cx.tower.jet.state",
        string="Current State",
        tracking=True,
        domain="[('id', 'in', jet_template_state_ids)]",
        copy=False,
    )
    state = fields.Char(
        related="state_id.reference",
        readonly=True,
        store=True,
        index=True,
        string="State Reference",
        help="Current state of the jet. "
        "NB: this is "
        "the reference of the state, not the name.",
    )
    jet_template_state_ids = fields.One2many(
        comodel_name="cx.tower.jet.state",
        compute="_compute_state_available_ids",
    )
    state_available_ids = fields.One2many(
        comodel_name="cx.tower.jet.state",
        compute="_compute_state_available_ids",
        help="Available states for the jet. "
        "Click on the button to transition to the state.",
        copy=False,
    )

    target_state_id = fields.Many2one(
        comodel_name="cx.tower.jet.state",
        string="Target State",
        readonly=True,
        copy=False,
        help="Destination state to which the jet is currently transitioning",
    )
    show_available_states = fields.Boolean(
        help="Show available states in the jet view",
        compute="_compute_show_available_states",
        inverse="_inverse_show_available_states",
        groups="cetmix_tower_server.group_manager",
    )
    action_available_ids = fields.Many2many(
        comodel_name="cx.tower.jet.action",
        compute="_compute_available_actions",
        string="Available Actions",
        help="Available actions for the jet. "
        "Click on the button to trigger the action.",
    )
    current_action_id = fields.Many2one(
        comodel_name="cx.tower.jet.action",
        string="Executing Action",
        readonly=True,
        copy=False,
    )
    current_command_log_id = fields.Many2one(
        comodel_name="cx.tower.command.log",
        string="Executing Command Log",
        groups="cetmix_tower_server.group_manager",
        readonly=True,
        copy=False,
    )

    # -- Waypoints
    is_waypoints_available = fields.Boolean(
        compute="_compute_is_waypoints_available",
        readonly=True,
    )
    waypoint_ids = fields.One2many(
        comodel_name="cx.tower.jet.waypoint",
        inverse_name="jet_id",
        string="Waypoints",
        help="Waypoints of the jet",
        copy=False,
    )
    waypoint_id = fields.Many2one(
        comodel_name="cx.tower.jet.waypoint",
        help="Current waypoint of the jet",
        readonly=True,
        copy=False,
        tracking=True,
    )

    # -- Variables used for configuration
    variable_value_ids = fields.One2many(
        inverse_name="jet_id",
    )

    # -- Logs
    command_log_ids = fields.One2many(
        comodel_name="cx.tower.command.log",
        inverse_name="jet_id",
        copy=False,
    )
    plan_log_ids = fields.One2many(
        comodel_name="cx.tower.plan.log",
        inverse_name="jet_id",
        copy=False,
    )

    # -- Access. Add relation for mixin fields
    user_ids = fields.Many2many(
        relation="cx_tower_jet_user_rel",
    )
    manager_ids = fields.Many2many(
        relation="cx_tower_jet_manager_rel",
    )

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   Compute methods
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    @api.depends("name", "state_id")
    def _compute_display_name(self):
        """Compute the display name of the jet"""
        for jet in self:
            jet.display_name = f"{jet.name} ({jet.state})" if jet.state else jet.name

    @api.depends("server_id")
    def _compute_jet_template_domain(self):
        """Compute the domain of the jet template"""
        for jet in self:
            jet.jet_template_domain = (
                [("server_ids", "in", [jet.server_id.id])] if jet.server_id else []
            )

    @api.depends("jet_template_id")
    def _compute_server_allowed_domain(self):
        """Compute the domain of the server allowed"""
        for jet in self:
            jet.server_allowed_domain = (
                [("id", "in", jet.jet_template_id.server_ids.ids)]
                if jet.jet_template_id and jet.jet_template_id.server_ids
                else []
            )

    @api.depends("jet_template_id", "jet_template_id.action_ids")
    def _compute_state_available_ids(self):
        """Compute the available states for the jet"""
        for jet in self:
            if not jet.jet_template_id:
                jet.update(
                    {
                        "jet_template_state_ids": False,
                        "state_available_ids": False,
                    }
                )
                continue
            actions = jet.jet_template_id.action_ids
            if not actions:
                jet.update(
                    {
                        "jet_template_state_ids": False,
                        "state_available_ids": False,
                    }
                )
                continue
            # Compute effective access level for the user
            effective_user_access_level = jet._get_user_effective_access_level()
            jet.update(
                {
                    "jet_template_state_ids": actions.state_from_id
                    | actions.state_transit_id
                    | actions.state_to_id,
                    "state_available_ids": (
                        actions.state_to_id - jet.state_id
                    ).filtered(
                        lambda s,
                        access_level=effective_user_access_level: s.access_level
                        <= access_level
                    ),
                }
            )

    @api.depends(
        "state_id",
        "jet_template_id",
        "jet_template_id.action_ids",
        "jet_template_id.action_ids.state_from_id",
        "jet_template_id.action_ids.state_to_id",
        "jet_template_id.action_ids.priority",
    )
    def _compute_available_actions(self):
        """Compute available actions based on current state and template"""
        for jet in self:
            if not jet.jet_template_id:
                jet.action_available_ids = False
                continue

            # Find actions in the template that start from the current state
            actions = jet.jet_template_id.action_ids.filtered(
                lambda a, state=jet.state_id: a.state_from_id == state
            )
            jet.update({"action_available_ids": actions})

    @api.depends("jet_template_id", "jet_template_id.template_requires_ids")
    def _compute_jet_requires_ids(self):
        """Compute the dependencies of the jets"""
        for jet in self:
            jet_template_dependencies = jet.jet_template_id.template_requires_ids

            final_vals = []

            # 1. Check removed dependencies
            if jet_template_dependencies:
                jet_dependencies_to_remove = jet.jet_requires_ids.filtered(
                    lambda d,
                    jtd=jet_template_dependencies: d.jet_template_dependency_id
                    not in jtd
                )
            else:
                jet_dependencies_to_remove = jet.jet_requires_ids

            if jet_dependencies_to_remove:
                final_vals = [(3, dep.id) for dep in jet_dependencies_to_remove]

            # Check new template dependencies
            if jet_template_dependencies:
                if jet.jet_requires_ids:
                    new_jet_template_dependencies = jet_template_dependencies.filtered(
                        lambda d, j=jet: d.id
                        not in j.jet_requires_ids.jet_template_dependency_id.ids
                    )
                else:
                    new_jet_template_dependencies = jet_template_dependencies
                for dep in new_jet_template_dependencies:
                    final_vals.append(
                        (
                            0,
                            0,
                            {
                                "jet_id": jet.id,
                                "jet_template_dependency_id": dep.id,
                            },
                        )
                    )
            if final_vals:
                jet.jet_requires_ids = final_vals

    @api.depends_context("uid")
    def _compute_show_available_states(self):
        """Compute if available states should be shown for the jet"""
        # Set all records at once to avoid multiple writes
        self.show_available_states = (
            self.env.user.cetmix_tower_show_jet_available_states
        )

    def _inverse_show_available_states(self):
        """Inverse the show available states for the jet"""
        for jet in self:
            if jet.show_available_states is not None:
                jet.env.user.cetmix_tower_show_jet_available_states = (
                    jet.show_available_states
                )

    @api.depends("jet_template_id", "jet_template_id.waypoint_template_ids")
    def _compute_is_waypoints_available(self):
        """Compute if waypoints are available for the jet"""
        for jet in self:
            jet.is_waypoints_available = bool(jet.jet_template_id.waypoint_template_ids)

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   Constraints
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    @api.constrains("server_id", "jet_template_id")
    def _check_jet_limit_per_server(self):
        """Check if the jet limit per server is reached"""
        for jet in self:
            if (
                jet.jet_template_id.limit_per_server
                and jet.jet_template_id.limit_per_server > 0
            ):
                if jet.jet_template_id.limit_per_server < len(
                    jet.jet_template_id.jet_ids.filtered(
                        lambda j, s=jet.server_id: j.server_id == s
                    )
                ):
                    raise ValidationError(
                        _(
                            "Jet limit per server reached for"
                            " '%(jet)s' on server '%(server)s'!",
                            jet=jet.display_name,
                            server=jet.server_id.display_name,
                        )
                    )

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   ORM methods
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    @api.model_create_multi
    def create(self, vals_list):
        """
        Create jets
        - Generate jet reference if not provided
        """

        for vals in vals_list:
            if not vals.get("reference"):
                vals["reference"] = generate_random_id(
                    sections=3, population=4, separator="_"
                )
        jets = super().create(vals_list)

        # Create server logs and scheduled tasks
        for jet in jets:
            # Server logs
            for server_log in jet.jet_template_id.server_log_ids:
                jet_log = server_log.copy(
                    {
                        "jet_id": jet.id,
                        "server_id": jet.server_id.id,
                        "jet_template_id": False,
                    }
                )
                if server_log.log_type == "file":
                    jet_log.file_id = server_log.file_template_id.create_file(
                        server=jet.server_id, jet=jet, if_file_exists="skip"
                    ).id

            # Scheduled tasks
            jet.scheduled_task_ids = jet.jet_template_id.scheduled_task_ids

        return jets

    def write(self, vals):
        """Handle the entry into the new state"""
        # Allow modifications in install mode only to load demo data
        if ("jet_template_id" in vals or "server_id" in vals) and not (
            self._context.get("install_mode") and self._context.get("install_xmlid")
        ):
            raise ValidationError(
                _(
                    "Jet template and server cannot be changed"
                    " once the jet is created!"
                )
            )
        if "state_id" in vals:
            for jet in self:
                jet._on_state_exit(state=jet.state_id)
            res = super().write(vals)
            for jet in self:
                jet._on_state_enter(state=jet.state_id)
        else:
            res = super().write(vals)
        return res

    def unlink(self):
        """
        Unlink all related files
        """

        # Check if the jet is deletable
        not_deletable_jets = self.filtered(lambda j: not j.deletable)
        if not_deletable_jets:
            raise ValidationError(
                _(
                    "Following jets cannot be deleted as they are not deletable: %s",
                    not_deletable_jets.mapped("display_name"),
                )
            )
        files = self.file_ids
        res = super().unlink()

        # Unlink files only after the records are deleted
        # This is done to avoid deleting the files while
        # the 'unlink' method fails due to some reason.
        if files:
            files.unlink()
        return res

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   Odoo Actions
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def action_run_command(self):
        """
        Returns wizard action to select command and run it
        """
        context = self.env.context.copy()
        context["default_jet_ids"] = self.ids
        return {
            "type": "ir.actions.act_window",
            "name": _("Run Command"),
            "res_model": "cx.tower.command.run.wizard",
            "view_mode": "form",
            "target": "new",
            "context": context,
        }

    def action_run_flight_plan(self):
        """
        Returns wizard action to select flightplan and run it
        """
        context = self.env.context.copy()
        context["default_jet_ids"] = self.ids
        return {
            "type": "ir.actions.act_window",
            "name": _("Run Flight Plan"),
            "res_model": "cx.tower.plan.run.wizard",
            "view_mode": "form",
            "target": "new",
            "context": context,
        }

    def action_open_command_logs(self):
        """
        Open current server command log records
        """
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_command_log"
        )
        action["domain"] = [("jet_id", "=", self.id)]  # pylint: disable=no-member
        return action

    def action_open_plan_logs(self):
        """
        Open current server flightplan log records
        """
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_plan_log"
        )
        action["domain"] = [("jet_id", "=", self.id)]  # pylint: disable=no-member
        return action

    def action_open_state_wizard(self):
        """Open the jet state wizard"""
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

    def action_open_files(self):
        """
        Open files of the current server
        """
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.cx_tower_file_action"
        )
        action["domain"] = [("jet_id", "=", self.id)]  # pylint: disable=no-member

        context = self._context.copy()
        if "context" in action and isinstance((action["context"]), str):
            context.update(ast.literal_eval(action["context"]))
        else:
            context.update(action.get("context", {}))

        # Remove group_by from context
        context.pop("group_by", None)
        context.update(
            {
                "default_jet_id": self.id,
                "default_server_id": self.server_id.id,
            }
        )
        action["context"] = context
        return action

    def action_open_requires_jets(self):
        """
        Open required jets of the current jet
        """
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.cx_tower_jet_action"
        )
        action["domain"] = [("jet_required_by_ids.jet_id", "=", self.id)]  # pylint: disable=no-member
        return action

    def action_open_required_by_jets(self):
        """
        Open dependant jets of the current jet
        """
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.cx_tower_jet_action"
        )
        action["domain"] = [("jet_requires_ids.jet_depends_on_id", "=", self.id)]  # pylint: disable=no-member
        return action

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #  General functions
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def _get_user_effective_access_level(self):
        """
        Get the effective access level for the current user.
        If user is manager but is not added as a manager to the jet,
        his access level is considered as user.
        Returns:
            str: The effective access level for the current user.
                see _selection_access_level() in cx.tower.access.mixin
        """
        self.ensure_one()
        user_access_level = self.env.user._cetmix_tower_access_level()
        if user_access_level == "2" and self.env.user not in self.manager_ids:
            return "1"
        return user_access_level

    def get_variable_value(self, variable_reference, no_fallback=False):
        """
        Return the value of a variable for the current jet.
        NB: this function follows the value application order.
        Jet->Jet Template->Server->Global

        Args:
            variable_reference (Char): The reference of the variable
                to get the value for
            no_fallback (bool): If True, will return current record value
                without checking fallback values.

        Returns:
            str: The value of the variable for the current record or None
        """
        self.ensure_one()
        if no_fallback:
            return super().get_variable_value(variable_reference, no_fallback)
        variable = self.env["cx.tower.variable"].get_by_reference(variable_reference)
        if not variable:
            return None
        values = variable._get_variable_values_by_references(
            variable_references=[variable_reference], jet=self
        )
        return values[variable_reference]

    def run_command(
        self,
        command,
        path=None,
        sudo=None,
        ssh_connection=None,
        **kwargs,
    ):
        """Run command on selected Jet.
        A helper function that calls the corresponding server function.

        Important: this method raises an exception if the jet
        is currently executing an action.
        You should handle this exception in your code.

        Args:
            command (cx.tower.command()): Command record
            path (Char): directory where command is run.
                Provide in case you need to override default command value
            sudo (Boolean): use sudo
                Defaults to None
            ssh_connection (SSH client instance, optional): SSH connection.
                Pass to reuse existing connection.
                This is useful in case you would like to speed up
                the ssh command running.        Returns:

        Returns:
            dict(): command running result if `no_command_log`
                context value == True else None
        """
        self.ensure_one()

        # Raise an exception if jets is currently executing an action
        if self.current_action_id:
            raise ValidationError(
                _(
                    "Jet '%(jet)s' is currently executing an action",
                    jet=self.display_name,
                )
            )

        return self.server_id.run_command(
            command=command,
            path=path,
            sudo=sudo,
            ssh_connection=ssh_connection,
            jet=self,
            **kwargs,
        )

    def run_flight_plan(self, flight_plan, jet_template=None, **kwargs):
        """
        Runs flight plan on the current jet.

        Important: this method raises an exception if the jet
        is currently executing an action.
        You should handle this exception in your code.

        Args:
            flight_plan (cx.tower.plan()): flight plan to run
            jet_template (cx.tower.jet.template()): jet template
                to run the flight plan on
            kwargs (dict): Optional arguments
                Following are supported but not limited to:
                    - "plan_log": {values passed to flightplan logger}
                    - "log": {values passed to logger}
                    - "key": {values passed to key parser}
                    - "variable_values", dict(): custom variable values
                        in the format of `{variable_reference: variable_value}`
                        eg `{'odoo_version': '16.0'}`
                        Will be applied only if user has write access to the server.
        Raises:
            ValidationError: If the jet is currently executing an action.
        Returns:
            log_record (cx.tower.plan.log()): plan log record
        """

        self.ensure_one()

        # Raise an exception if jets is currently executing an action
        # TODO: keep an eye on this method in case we use it
        # directly in actions.
        if self.current_action_id:
            raise ValidationError(
                _(
                    "Jet '%(jet)s' is currently executing an action",
                    jet=self.display_name,
                )
            )

        return self.server_id.run_flight_plan(
            flight_plan=flight_plan,
            jet_template=jet_template,
            jet=self,
            **kwargs,
        )

    def bring_to_state(self, state_reference):
        """
        Bring the jet to a specific state.
        This is a wrapper around the _bring_to_state method meant to be used
        in various automatic actions.

        IMPORTANT: alway prefer using this method over the _bring_to_state method
        in automation (eg Python commands) because it will check the access level
        of the user to the state and raise an exception if the user is not allowed
        to set the state.

        Use `_bring_to_state` method directly if you want to provide a state
        object instead of a reference.

        Args:
            state_reference (Char): The reference of the state to bring the jet to.
        Returns:
            The jet is brought into the target state.
            In case of an error, the jet is brought into the error state
            if the latter is defined.

        Raises:
            ValidationError: If the state is not found.
            AccessError: If the user is not allowed to set the state.
        """
        self.ensure_one()
        state = self.env["cx.tower.jet.state"].get_by_reference(state_reference)
        if not state:
            raise ValidationError(
                _(
                    "State '%(state)s' not found for jet '%(jet)s'",
                    state=state_reference,
                    jet=self.display_name,
                )
            )

        if state.access_level > self._get_user_effective_access_level():
            raise AccessError(
                _("You are not allowed to set the '%(state)s' state!", state=state.name)
            )

        self._bring_to_state(state)

    def clone(self, server=None, name=None, state=None, **kwargs):
        """
        Create a new jet from this template on the given server.

        Following configuration variables will be available in the flight plan:
        `__original_jet__`: The reference of the original jet
        `__requested_state__`: The reference of the requested state
            the new jet was requested to be in.

        Use these variables in the flight plan to identify the original jet
        and the requested state.

        Args:
            server (cx.tower.server()): The server to clone the jet on.
                If not provided, the jet will be cloned on the same server.
            name (str): The name of the new jet.
                If not provided, a random name will be generated.
            state (cx.tower.jet.state()): The state to bring the new jet to.

        Kwargs:
            field values to populate in the new jet record.
            NB: configuration variables are provided as follows:
                (dict): Custom configuration variables
                Following format is used:
                    `variable_reference`: `variable_value_char`
                    eg:
                    {'branch': 'prod', 'odoo_version': '16.0'}
        Returns:
            cx.tower.jet(): The new jet or False if the cloning has failed
        """
        self.ensure_one()

        jet_template = self.jet_template_id
        if not server:
            server = self.server_id
            same_server = True
        else:
            same_server = server.id == self.server_id.id

        # Check if template allows cloning on the same server
        if same_server and not jet_template.plan_clone_same_server_id:
            raise ValidationError(
                _(
                    "Cloning on the same server is not allowed"
                    " for template '%(template)s'",
                    template=jet_template.name,
                )
            )
        # Check if template allows cloning to a different server
        if not same_server and not jet_template.plan_clone_different_server_id:
            raise ValidationError(
                _(
                    "Cloning to a different server is not allowed"
                    " for template '%(template)s'",
                    template=jet_template.name,
                )
            )
        # Check if the jet creation is allowed on the given server
        if not jet_template._allow_jet_creation(server):
            return False

        # Prepare the jet custom values
        kwargs.update(
            {
                "jet_cloned_from_id": self.id,
            }
        )

        # Create a new jet
        jet = jet_template.create_jet(
            server, name=name or self._default_cloned_jet_name(), **kwargs
        )

        # Set scheduled tasks of the original jet to the new jet
        jet.scheduled_task_ids = self.scheduled_task_ids

        # Set server logs of the original jet to the new jet
        # Delete the server logs of the new jet if the original jet
        # has no server logs
        if self.server_log_ids:
            jet.server_log_ids = [
                log.copy({"jet_id": False, "server_id": False}).id
                for log in self.server_log_ids
            ]
            # Create files for file-type server logs
            for jet_log in jet.server_log_ids:
                if jet_log.log_type == "command":
                    continue
                if jet_log.log_type == "file":
                    jet_log.file_id = jet_log.file_template_id.create_file(
                        server=jet.server_id, jet=jet, if_file_exists="skip"
                    ).id
        else:
            jet.server_log_ids.unlink()

        # NB: we are not passing the state as we need to run
        # the clone flight plan first.
        # The plan should take care of the state transition
        # using the configuration variables.
        # Update the custom values in the kwargs

        variable_values = {
            "__original_jet__": self.reference,
            "__original_server__": self.server_id.reference,
            "__requested_jet_state__": state.reference if state else None,
        }

        if same_server and jet_template.plan_clone_same_server_id:
            jet.run_flight_plan(
                jet_template.plan_clone_same_server_id, variable_values=variable_values
            )
        elif not same_server and jet_template.plan_clone_different_server_id:
            jet.run_flight_plan(
                jet_template.plan_clone_different_server_id,
                variable_values=variable_values,
            )

        return jet

    def _default_cloned_jet_name(self):
        """Return default cloned jet name"""
        self.ensure_one()
        return f"{self.name} (clone)"

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   Jet actions, state transitions, jet requests
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def _trigger_action(
        self, action, from_transition=False, raise_if_not_available=True, **kwargs
    ):
        """Trigger an action on the jet.

        The function flow is:

        1. Bring the jet into the transit state.
        2. Execute the flight plan if defined.
        3. Bring the jet into the target state.

        Success:
            The jet is brought into the target state.

        Error:
            The jet is brought into the error state if it is defined.
            Otherwise, the jet is brought into the initial state.


        Args:
            action (cx.tower.jet.action()): The action to trigger
            from_transition (bool): True if the action is triggered
                from a transition.
                This is used to distinguish between a user directly
                triggering the action and a transition from one state
                to another.
            raise_if_not_available (bool):
                True if the function should raise an exception
                if the action is not available for this jet.
            **kwargs: Additional arguments:
                - current_command_log: Optional command log record to track execution

        Returns:
            dict: A dictionary with the following keys:
                - status: The status of the action
                - error: The error message if the action is not available

        Raises:
            ValidationError: If the action is not available for this jet.
        """
        self.ensure_one()

        # TODO: put action in the queue if jet is busy

        # Action properties must be accessible despite of the user group
        action = action.sudo()

        # Get current command log
        current_command_log = kwargs.get("current_command_log")

        # Ensure the action is available for this jet
        if action.id not in self.action_available_ids.ids:
            error = _(
                "Action '%(action)s' is not available for jet"
                " '%(jet)s' in state '%(state)s'",
                action=action.name,
                jet=self.name,  # pylint: disable=no-member
                state=self.state_id.name if self.state_id else _("Undefined"),
            )
            if raise_if_not_available:
                raise ValidationError(error)
            if current_command_log:
                current_command_log.finish(
                    status=JET_ACTION_NOT_AVAILABLE,
                    error=error,
                )
            return {"status": JET_ACTION_NOT_AVAILABLE, "error": error}

        # Update the jet state
        transit_state = action.state_transit_id
        target_state = action.state_to_id

        # Check if the jet is already in the target state
        # TODO: handle the case when destination state
        # is the same as the current state.
        # Eg when a jet is restarted.
        if self.state_id == target_state and from_transition:
            self.sudo().write({"target_state_id": None})
            self._finalize_transition(failed=False)
            return {"status": 0, "error": None}

        # Set target state if not already set
        if not self.target_state_id:
            self.sudo().write({"target_state_id": target_state})

        # Check if all dependencies are satisfied
        # if starting from an undefined state.
        # This is typical for a newly created jet.
        if not self.state_id and not self._control_dependencies():
            # The process will be resumed
            # when the dependencies are satisfied
            error = _("Jet dependencies are not satisfied")
            if current_command_log:
                current_command_log.finish(
                    status=JET_DEPENDENCIES_NOT_SATISFIED,
                    error=error,
                )
            return {"status": JET_DEPENDENCIES_NOT_SATISFIED, "error": error}

        self.sudo().write(
            {
                "state_id": transit_state,
                "current_action_id": action.id,
                "current_command_log_id": current_command_log.id
                if current_command_log
                else False,
            }
        )
        if action.plan_id:
            # Run the flight plan
            plan_kwargs = {
                "plan_log": {
                    "jet_action_id": action.id,
                },
            }
            # Populate custom variable values from current command log
            current_command_log = self.current_command_log_id
            if current_command_log and current_command_log.variable_values:
                plan_kwargs["variable_values"] = current_command_log.variable_values

            # Run the flight plan
            with self.env.cr.savepoint():
                self.server_id.sudo().run_flight_plan(
                    flight_plan=action.plan_id,
                    jet=self,
                    **plan_kwargs,
                )
                # Flight plan will trigger the `_flight_plan_finished` function again
                # if the flight plan is finished successfully.
                # So we don't need continue the loop in this case.
                return {"status": 0, "error": None}

        # Set the state to the destination state if no plan is defined
        final_vals = {
            "state_id": target_state,
            "current_action_id": False,
        }

        # Reset the target state if the jet has reached the target state
        if target_state == self.target_state_id:
            final_vals["target_state_id"] = None

        self.sudo().write(final_vals)

        # Continue the chain of actions if the final state is not reached yet
        if self.target_state_id:
            self._bring_to_state(self.target_state_id)

        # Trigger the transition finished event
        self._finalize_transition(failed=False)
        return {"status": 0, "error": None}

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

        IMPORTANT: this method uses sudo() to bypass access rules.
        This means that this method must be used with caution and only in cases
        where the access level is not important.
        For external automation including Python commands always prefer using
        the bring_to_state() method instead.
        For example:
        ```python
        jet = self.env["cx.tower.jet"].browse(jet_id)
        jet.bring_to_state(state_reference)
        ```

        Args:
            state (cx.tower.jet.state()): The state to bring the jet to

        Returns:
            The jet is brought into the first state of the path.
            In case of an error, the jet is brought into the error state
            if the latter is defined.

        Raises:
            ValidationError: If the path is not found.
        """
        self.ensure_one()

        # Use sudo to bypass access rules
        self = self.sudo()

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
                    state=state.name if state else _("Undefined"),
                )
            )

        # Set the target state if not already set
        if not self.target_state_id:
            self.write(
                {
                    "target_state_id": state,
                }
            )

        # Trigger the first action in the path
        self._trigger_action(path[0], from_transition=True)

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
            if self.target_state_id == self.current_action_id.state_to_id:
                vals["target_state_id"] = None

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
                    "target_state_id": None,
                }
            )
            transition_failed = True

        self.sudo().write(vals)

        # Continue the chain of actions if the final state is not reached yet
        if self.target_state_id:
            self._bring_to_state(self.target_state_id)
        else:
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
        if self.served_jet_request_id:
            self.served_jet_request_id._finalize(failed=failed)

        # 2. Finalize the command log if transition was
        # triggered from a command
        command_log = self.current_command_log_id
        if command_log:
            # Reset the current command log id
            # Using sudo to bypass write access rules
            self.sudo().write({"current_command_log_id": False})

            # Prepare the command log finish values
            if failed:
                error = _(
                    "Action failed for jet %(jet)s.",
                    jet=self.name,  # pylint: disable=no-member
                )
                response = None
                status = JET_STATE_ERROR
            else:
                response = _(
                    "Jet %(jet)s was moved to the '%(state)s' state.",
                    jet=self.name,  # pylint: disable=no-member
                    state=self.state_id.name if self.state_id else _("Undefined"),
                )
                status = 0
                error = None

            # Finish the command log
            command_log.finish(
                status=status,
                response=response,
                error=error,
            )

        # 3. Notify the jet that it is available
        self._on_is_available()

    def _serve_jet_request(self, jet_request):
        """
        Serve a jet request.

        Args:
            jet_request (cx.tower.jet.request()): The jet request to serve
        """
        self.ensure_one()

        # Save the request
        # Using sudo to bypass write access rules
        self.sudo().write({"served_jet_request_id": jet_request.id})

        # State is reached, finalize the request
        if self.state_id == jet_request.state_requested_id:
            jet_request._finalize(failed=False)
        else:
            # Trigger the jet to bring itself to the required state
            jet_request.state = "processing"
            self._bring_to_state(jet_request.state_requested_id)

    def _finalize_jet_request(self, jet_request):
        """
        This function is called when a jet request issued by this jet is finalized.

        Args:
            jet_request (cx.tower.jet.request()): The jet request that was finalized
        """
        self.ensure_one()

        # On success, update the dependency and
        if jet_request.state == "success":
            # Update the dependency if the request was for a dependency
            dependency = jet_request.for_dependency_id
            if dependency:
                dependency.jet_depends_on_id = jet_request.jet_id
            # Proceed with the state transition if all dependencies are satisfied
            # and the transition is still in progress
            if self._control_dependencies() and self.target_state_id:
                self._bring_to_state(self.target_state_id)
        else:
            # Stop transition if the request failed
            # Using sudo to bypass write access rules
            self.sudo().write({"target_state_id": False})
            # Mark served jet request as failed
            if self.served_jet_request_id:
                self.served_jet_request_id._finalize(failed=True)

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   Waypoints
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def create_waypoint(
        self,
        waypoint_template,
        name=None,
        fly_here=False,
        ignore_busy=False,
        created_from_command_log=None,
        **metadata,
    ):
        """Create a new waypoint for the jet.

        The jet must not be busy unless ignore_busy is True.
        When created_from_command_log is provided, the waypoint stores it so that
        the waypoint callback can finish the command log when the waypoint
        reaches ready/current or error.

        Args:
            waypoint_template (cx.tower.jet.waypoint.template or str):
                The waypoint template or reference to create the waypoint from.
            name (str, optional): The name of the waypoint. Defaults to None.
            fly_here (bool, optional): Whether to fly to the waypoint after creation.
                Defaults to False.
            ignore_busy (bool, optional): Whether to ignore the busy state and create
                the waypoint anyway.
                Useful when creating waypoints from jet actions.
                Defaults to False.
            created_from_command_log (cx.tower.command.log, optional): Command log
                that created this waypoint; the waypoint callback will finish it.
                Defaults to None.
            **metadata: Additional metadata to pass to the waypoint.

        Returns:
            cx.tower.jet.waypoint

        Raises:
            ValidationError: If the waypoint template is not found
            or does not belong to the jet template, or if the jet is busy.
        """
        self.ensure_one()

        # Check if the jet is busy
        if self._is_busy() and not ignore_busy:
            _logger.error(
                "Cannot create waypoint for jet %s because it is busy", self.name
            )
            raise ValidationError(
                _("Cannot create waypoint for jet %s because it is busy", self.name)
            )

        # Resolve the waypoint template
        if isinstance(waypoint_template, str):
            waypoint_reference = waypoint_template
            waypoint_template = self.env[
                "cx.tower.jet.waypoint.template"
            ].get_by_reference(waypoint_reference)
            if not waypoint_template:
                _logger.error("Waypoint template %s not found", waypoint_reference)
                raise ValidationError(
                    _("Waypoint template %s not found", waypoint_reference)
                )

        # Check if the waypoint template belongs to the jet template
        if waypoint_template.jet_template_id != self.jet_template_id:
            _logger.error(
                "Waypoint template %s does not belong to the jet template %s",
                waypoint_template.name,
                self.jet_template_id.name,
            )
            raise ValidationError(
                _(
                    "Waypoint template %(waypoint_template)s does not belong "
                    "to the jet template %(jet_template)s",
                    waypoint_template=waypoint_template.name,
                    jet_template=self.jet_template_id.name,
                )
            )

        # Prepare the waypoint values
        waypoint_values = self._prepare_waypoint_values(
            waypoint_template=waypoint_template,
            name=name,
            **metadata,
        )
        if created_from_command_log:
            waypoint_values["created_from_command_log_id"] = created_from_command_log.id

        # Create the waypoint
        waypoint = self.env["cx.tower.jet.waypoint"].create(waypoint_values)
        waypoint.prepare(is_destination=fly_here)
        return waypoint

    def _prepare_waypoint_values(self, waypoint_template, name=None, **metadata):
        """Prepare the waypoint values

        Args:
            waypoint_template (cx.tower.jet.waypoint.template): The waypoint template
            name (Char, optional): The name of the waypoint.
        """
        self.ensure_one()

        # Prepare the waypoint values
        vals = {
            "waypoint_template_id": waypoint_template.id,
            "name": name if name else _("Auto-generated waypoint"),
            "jet_id": self.id,
        }
        if metadata:
            vals["metadata"] = metadata

        return vals

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   Event handling
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

        # Refresh the frontend views
        self.env.user.reload_views(model="cx.tower.jet", rec_ids=[self.id])

    def _on_jet_request_completed(self, jet_request):
        """
        Handle the completion of a jet request.
        """
        self.ensure_one()
        # TODO: Implement the logic to handle the completion of a jet request
        pass

    def _on_is_available(self):
        """
        Handle the event when the jet is not busy anymore.
        """

        # Process pending requests
        jet_request_obj = self.env["cx.tower.jet.request"].sudo()

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
                request._finalize(failed=False)

            # Pick the first request that requests a different state
            remaining_requests = explicit_requests - same_state_requests
            if remaining_requests:
                self._serve_jet_request(remaining_requests[0])
                return

        # 2. Requests where the jet is requested implicitly via template
        if self._accepts_new_links():
            implicit_requests = jet_request_obj.search(
                [
                    ("server_id", "=", self.server_id.id),  # pylint: disable=no-member
                    ("jet_template_id", "=", self.jet_template_id.id),  # pylint: disable=no-member
                    ("jet_id", "=", False),
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
                    request._finalize(failed=False)

            # Pick the first request that requests a different state
            remaining_requests = implicit_requests - same_state_requests
            if remaining_requests:
                remaining_request = remaining_requests[0]
                # Set current jet as the target jet for the request
                remaining_request.write({"jet_id": self.id})  # pylint: disable=no-member
                self._serve_jet_request(remaining_request)
                return

        # Send success notification when everything is done
        # Use context timestamp to avoid timezone issues
        context_timestamp = fields.Datetime.context_timestamp(
            self, fields.Datetime.now()
        )

        # Check if notifications are enabled
        ICP_sudo = self.env["ir.config_parameter"].sudo()
        notification_type_success = ICP_sudo.get_param(
            "cetmix_tower_server.notification_type_success"
        )
        if notification_type_success:
            # Action for button
            action = self.env["ir.actions.act_window"]._for_xml_id(
                "cetmix_tower_server.cx_tower_jet_action"
            )

            context = self.env.context.copy()
            params = dict(context.get("params") or {})
            params["button_name"] = _("View Jet")
            context["params"] = params

            # Add record id and context to the action
            action.update(
                {
                    "context": context,
                    "res_id": self.id,
                    "views": [(False, "form")],
                }
            )
            # Send success notification
            self.env.user.notify_success(
                message=_(
                    "%(timestamp)s<br/>" "Available in the '%(name)s' state",
                    name=self.state_id.name if self.state_id else _("Undefined"),
                    timestamp=context_timestamp,
                ),
                title=self.name,
                sticky=notification_type_success == "sticky",
                action=action,
            )

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
        busy = bool(self.target_state_id)
        return busy

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   Manage dependencies
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def _control_dependencies(self):
        """
        Check if dependencies are satisfied.
        If some dependencies are missing, it creates a new jet request to ensure
        that a jet that is required by that dependency is available.

        Returns:
            bool: True if all dependencies are satisfied, False otherwise
        """
        self.ensure_one()

        all_dependencies_satisfied = True

        jet_request_obj = self.env["cx.tower.jet.request"]

        # Check if jets are present in the required state
        for jet_dependency in self.jet_requires_ids:
            jet_template_dependency = jet_dependency.jet_template_dependency_id
            if (
                jet_dependency.jet_depends_on_id
                and jet_dependency.jet_depends_on_id.state_id
                == jet_template_dependency.state_required_id
            ):
                # The dependency is satisfied, continue to the next dependency
                continue

            # Create a new jet request to ensure we have the required jet
            #  in the required state
            jet_request_obj._create_request(
                server=self.server_id,
                jet_template=jet_template_dependency.template_required_id,
                state=jet_template_dependency.state_required_id,
                requested_by_jet=self,
                for_dependency=jet_dependency,
            )
            # Stop here as it will be resumed when the jet request is finalized
            all_dependencies_satisfied = False
            break

        return all_dependencies_satisfied

    def _get_dependent_jets_by_template(self, jet_template):
        """
        Check all dependencies of the jet and returns all jets
        of the given template.
        Both dependent and this jet depends on jets are returned.

        Args:
            jet_template (cx.tower.jet.template()): The jet template

        Returns:
            cx.tower.jet(): Recordset of jets
        """
        self.ensure_one()

        # Check L1 jets this jet depends on
        l1_jets = self.jet_requires_ids.filtered(
            lambda r: r.jet_depends_on_id.jet_template_id == jet_template
        ).jet_depends_on_id
        # Check L1 jets that depend on this jet
        l2_jets = self.jet_required_by_ids.filtered(
            lambda r: r.jet_id.jet_template_id == jet_template
        ).jet_id

        # TODO: check the entire dependency tree
        return l1_jets | l2_jets

    def get_dependent_jets_by_template_reference(self, jet_template_reference):
        """
        A wrapper for _get_dependent_jets_by_template that allows
        to use the reference of the jet template instead of the record.
        Designed to be used in the Python commands.

        Args:
            jet_template_reference (str): The reference of the jet template

        Returns:
            cx.tower.jet(): Recordset of jets with the given template
            that depend on the current jet.
        """
        self.ensure_one()

        jet_template = self.jet_template_id.get_by_reference(jet_template_reference)
        if jet_template:
            return self._get_dependent_jets_by_template(jet_template)
        return False

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   Access role mixin functions
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def _get_post_create_fields(self):
        """
        Add fields that should be populated after jet template creation
        """
        res = super()._get_post_create_fields()
        return res + ["variable_value_ids", "server_log_ids"]
