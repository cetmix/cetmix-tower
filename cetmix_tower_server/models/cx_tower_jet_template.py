# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import ast
import base64
import heapq
import logging
import xml.etree.ElementTree as ET
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .tools import generate_random_id, is_valid_url

_logger = logging.getLogger(__name__)


# Maximum number of retries to generate a unique jet name
# Used to prevent infinite loop
MAX_JET_NAME_RETRIES = 50


class CxTowerJetTemplate(models.Model):
    """Jet Templates are templates to create and manage jets"""

    _name = "cx.tower.jet.template"
    _description = "Cetmix Tower Jet Template"
    _inherit = [
        "cx.tower.reference.mixin",
        "cx.tower.access.mixin",
        "cx.tower.access.role.mixin",
        "cx.tower.variable.mixin",
        "mail.thread",
        "cx.tower.tag.mixin",
    ]
    _order = "name asc"
    _mail_post_access = "read"

    active = fields.Boolean(default=True)
    icon = fields.Image(
        string="Icon image",
        max_width=128,
        max_height=128,
        help="Icon of the related product to make navigation easier. "
        "E.g. Docker logo for the Docker jet template.",
    )
    note = fields.Text()

    # ---- Access. Add relation for mixin fields
    user_ids = fields.Many2many(
        relation="cx_tower_jet_template_user_rel",
    )
    manager_ids = fields.Many2many(
        relation="cx_tower_jet_template_manager_rel",
    )

    # Jets
    jet_ids = fields.One2many(
        comodel_name="cx.tower.jet",
        inverse_name="jet_template_id",
        string="Jets",
        copy=False,
    )
    jet_count = fields.Integer(compute="_compute_jet_count", store=False)

    # Servers
    server_ids = fields.Many2many(
        comodel_name="cx.tower.server",
        relation="cx_tower_jet_template_server_rel",
        column1="jet_template_id",
        column2="server_id",
        string="Installed on Servers",
        readonly=True,
        help="These servers have this jet template installed",
        copy=False,
    )
    limit_per_server = fields.Integer(
        string="Limit per Server",
        help="Maximum number of Jets that can be launched on a server. "
        "Set to 0 for no limit.",
    )
    file_ids = fields.One2many(
        comodel_name="cx.tower.file",
        inverse_name="jet_template_id",
        string="Files",
        help="Files of this jet template",
        copy=False,
    )

    # Wizards
    show_in_create_wizard = fields.Boolean(
        string="Show in Wizard",
        help="If enabled, the template will be shown "
        "in the wizard to create a new jet",
    )

    # Flight Plans
    plan_install_id = fields.Many2one(
        comodel_name="cx.tower.plan",
        string="Installation Flight Plan",
        help="Flight plan used to install the template from a server",
    )
    plan_uninstall_id = fields.Many2one(
        comodel_name="cx.tower.plan",
        string="Uninstallation Flight Plan",
        help="Flight plan used to uninstall the template from a server",
    )
    plan_clone_same_server_id = fields.Many2one(
        comodel_name="cx.tower.plan",
        help="Flight plan used to clone the jet on the same server",
    )
    plan_clone_different_server_id = fields.Many2one(
        comodel_name="cx.tower.plan",
        help="Flight plan used to clone the jet to a different server",
    )

    # Logs
    command_log_ids = fields.One2many(
        comodel_name="cx.tower.command.log",
        inverse_name="jet_template_id",
        copy=False,
    )
    plan_log_ids = fields.One2many(
        comodel_name="cx.tower.plan.log",
        inverse_name="jet_template_id",
        copy=False,
    )

    # Server logs
    server_log_ids = fields.One2many(
        comodel_name="cx.tower.server.log",
        inverse_name="jet_template_id",
        copy=True,
    )
    # Scheduled Tasks
    scheduled_task_ids = fields.Many2many(
        comodel_name="cx.tower.scheduled.task",
        relation="cx_tower_jet_template_scheduled_task_rel",
        column1="jet_template_id",
        column2="scheduled_task_id",
        string="Scheduled Tasks",
        copy=True,
    )

    # Configuration variables
    variable_value_ids = fields.One2many(
        inverse_name="jet_template_id",
        copy=True,
    )

    # Actions
    action_ids = fields.One2many(
        comodel_name="cx.tower.jet.action",
        inverse_name="jet_template_id",
        string="Lifecycle Actions",
        copy=True,
    )
    action_create_id = fields.Many2one(
        comodel_name="cx.tower.jet.action",
        string="Create Jet",
        help="The action is used to create a new Jet",
        compute="_compute_border_actions",
        readonly=False,
        store=True,
        domain="[('state_from_id', '=', False), "
        "('state_to_id', '!=', False),"
        " ('jet_template_id', '=', id)]",
        copy=False,
    )
    action_destroy_id = fields.Many2one(
        comodel_name="cx.tower.jet.action",
        string="Destroy Jet",
        compute="_compute_border_actions",
        readonly=False,
        store=True,
        help="The action is used to destroy a Jet",
        domain="[('state_to_id', '=', False), ('jet_template_id', '=', id)]",
        copy=False,
    )

    # Dependencies
    template_requires_ids = fields.One2many(
        comodel_name="cx.tower.jet.template.dependency",
        inverse_name="template_id",
        string="Requires",
        help="Define other templates that must be in specific"
        " states for this template to function",
        copy=True,
        groups="cetmix_tower_server.group_manager",
    )
    template_required_by_ids = fields.One2many(
        comodel_name="cx.tower.jet.template.dependency",
        inverse_name="template_required_id",
        string="Required by",
        help="Define other templates that require this template"
        " to be in a specific"
        " state to function",
        groups="cetmix_tower_server.group_manager",
    )

    # Installation
    install_ids = fields.One2many(
        comodel_name="cx.tower.jet.template.install.line",
        inverse_name="jet_template_id",
        string="Installations",
        help="Installations of the template",
        auto_join=True,
        copy=False,
        groups="cetmix_tower_server.group_manager",
        readonly=True,
    )

    # Waypoints
    waypoint_template_ids = fields.One2many(
        comodel_name="cx.tower.jet.waypoint.template",
        inverse_name="jet_template_id",
        string="Waypoints",
        help="Waypoints of the template",
        copy=True,
    )

    # Dependency Graph
    # Odoo blocks SVG images in fields.Binary,
    # so we use fields.Char to store the SVG content
    # https://github.com/odoo/odoo/blob/c27d978ade9bcbea056933d8fb8b5a924e983bde/odoo/fields.py#L2321
    dependency_graph_svg = fields.Char(
        compute="_compute_dependency_graph_svg",
        store=True,
        recursive=True,
        copy=False,
        help="SVG image content of the dependency graph of the template",
    )
    dependency_graph_image = fields.Binary(
        string="Dependency Graph",
        compute="_compute_dependency_graph_image",
        compute_sudo=True,
        help="SVG image of the dependency graph of the template",
    )

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   Compute functions
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    @api.depends("jet_ids")
    def _compute_jet_count(self):
        """Compute the number of jets for each template."""
        for template in self:
            template.jet_count = len(template.jet_ids)

    @api.depends(
        "action_ids",
        "action_ids.state_from_id",
        "action_ids.state_to_id",
        "action_ids.priority",
    )
    def _compute_border_actions(self):
        """Compute the 'Create Jet' and 'Destroy Jet' actions"""
        for template in self:
            # If no initial state, add the one automatically
            if not template.action_create_id:
                # Has no initial state and has a final state
                suitable_actions = template.action_ids.filtered(
                    lambda a: not a.state_from_id and a.state_to_id
                ).sorted("priority")
                # Take the first one (lowest priority = highest priority)
                if suitable_actions:
                    template.action_create_id = suitable_actions[0]

            # If "Create" action has an initial state
            # or does not have a final state
            # it cannot be used to create a new Jet
            elif (
                template.action_create_id.state_from_id
                or not template.action_create_id.state_to_id
            ):
                template.action_create_id = False

            if not template.action_destroy_id:
                # Has no final state
                suitable_actions = template.action_ids.filtered(
                    lambda a: not a.state_to_id
                ).sorted("priority")
                # Take the first one (lowest priority = highest priority)
                if suitable_actions:
                    template.action_destroy_id = suitable_actions[0]

            # If "Destroy" action has a final state
            # it cannot be used to destroy a Jet
            elif template.action_destroy_id.state_to_id:
                template.action_destroy_id = False

    @api.depends(
        "template_requires_ids",
        "template_requires_ids.state_required_id",
        "template_requires_ids.template_required_id.dependency_graph_image",
    )
    def _compute_dependency_graph_svg(self):
        """Compute dependency graph image using SVG generation"""
        for template in self:
            try:
                graph_data = template._build_dependency_graph()
                svg_content = template._generate_svg_graph(graph_data)
                template.dependency_graph_svg = svg_content
            except Exception as e:
                _logger.error(
                    f"Error generating dependency graph "
                    f"for template {template.name}: {e}"
                )
                template.dependency_graph_svg = False

    @api.depends("dependency_graph_svg")
    def _compute_dependency_graph_image(self):
        for template in self:
            template.dependency_graph_image = template.dependency_graph_svg

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   ORM methods
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def unlink(self):
        """
        Unlink all related files
        """

        # Don't allow to unlink a template if it has any jets
        # or is installed on any server
        templates_with_jets = self.filtered(lambda t: t.jet_ids)
        if templates_with_jets:
            raise ValidationError(
                _(
                    "Following templates cannot be deleted "
                    "as they still have jets: %s",
                    templates_with_jets.mapped("display_name"),
                )
            )
        templates_with_installed_servers = self.filtered(lambda t: t.server_ids)
        if templates_with_installed_servers:
            raise ValidationError(
                _(
                    "Following templates cannot be deleted "
                    "as they are installed on servers: %s",
                    ",".join(templates_with_installed_servers.mapped("display_name")),
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

    def action_install_on_servers(self):
        """Action to install the Jet Template on the selected servers."""
        self.ensure_one()
        # Open the wizard to install the template on the selected servers
        return {
            "type": "ir.actions.act_window",
            "name": _("Install on Servers"),
            "res_model": "cx.tower.jet.template.install.wiz",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_jet_template_id": self.id,
            },
        }

    def action_uninstall_from_server(self, server=None):
        """Action to uninstall the Jet Template from the selected servers."""
        self.ensure_one()
        # Open the wizard to uninstall the template from the selected servers
        if not server:
            server_id = self.env.context.get("server_id")
            server = self.env["cx.tower.server"].browse(server_id)
        if not server:
            raise ValidationError(_("No server selected"))
        return self.uninstall_from_servers(servers=server)

    def action_open_command_logs(self):
        """
        Open current server command log records
        """
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_command_log"
        )
        action["domain"] = [("jet_template_id", "=", self.id)]  # pylint: disable=no-member
        return action

    def action_open_plan_logs(self):
        """
        Open current server flightplan log records
        """
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_plan_log"
        )
        action["domain"] = [("jet_template_id", "=", self.id)]  # pylint: disable=no-member
        return action

    def action_open_files(self):
        """
        Open files of the current server
        """
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.cx_tower_file_action"
        )
        action["domain"] = [("jet_template_id", "=", self.id)]  # pylint: disable=no-member

        context = self._context.copy()
        if "context" in action and isinstance((action["context"]), str):
            context.update(ast.literal_eval(action["context"]))
        else:
            context.update(action.get("context", {}))

        context.update(
            {
                "default_jet_template_id": self.id,  # pylint: disable=no-member
                "search_default_group_by_jet_id": 1,
            }
        )
        action["context"] = context
        return action

    def action_open_jets(self):
        """
        Open jets of the current jet template
        """
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.cx_tower_jet_action"
        )
        context = self._context.copy()
        if "context" in action and isinstance((action["context"]), str):
            context.update(ast.literal_eval(action["context"]))
        else:
            context.update(action.get("context", {}))

        context.update(
            {
                "default_jet_template_id": self.id,  # pylint: disable=no-member
                "group_by": "server_id",
            }
        )
        action["domain"] = [("jet_template_id", "=", self.id)]  # pylint: disable=no-member
        action["context"] = context
        return action

    def action_new_jet(self):
        """
        Returns wizard action to launch a jet
        """
        context = self.env.context.copy()
        context.update(
            {
                "default_jet_template_id": self.id
                if self.show_in_create_wizard
                else False,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Launch New Jet"),
            "res_model": "cx.tower.jet.create.wizard",
            "view_mode": "form",
            "target": "new",
            "context": context,
        }

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #  General functions
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def get_variable_value(self, variable_reference, no_fallback=False):
        """
        Return the value of a variable for the current jet.
        NB: this function follows the value application order.
        Jet Template->Server->Global
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
            variable_references=[variable_reference], jet_template=self
        )
        return values[variable_reference]

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   Template Actions
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def _get_action_path(self, state_from=None, state_to=None):
        """Return the order of actions that lead from one state to another.
        If the initial state is not provided, must start with "Create Action".
        If the final state is not provided, must end with "Destroy Action".

        Args:
            state_from (cx.tower.jet.state()): State to start from
            state_to (cx.tower.jet.state()): State to end at

        Returns:
            list: List of actions that lead from one state to another
        """
        self.ensure_one()

        original_state_to = state_to
        path = []

        create_action = self.action_create_id if self.action_create_id else False
        destroy_action = self.action_destroy_id if self.action_destroy_id else False

        if not state_from:
            if not create_action:
                return []
            path.append(create_action)
            state_from = create_action.state_to_id

        if not state_to:
            if not destroy_action:
                return []
            state_to = destroy_action.state_from_id

        if state_from == state_to:
            if not original_state_to and destroy_action:
                return path + [destroy_action]
            return path

        adjacency = self._get_action_adjacency()
        state_path = self._find_action_path_bfs(state_from, state_to, adjacency)
        if state_path is not None:
            result_path = path + state_path
            if not original_state_to and destroy_action:
                result_path.append(destroy_action)
            return result_path

        if (
            not original_state_to
            and destroy_action
            and state_from == destroy_action.state_from_id
        ):
            return path + [destroy_action]

        return []

    def _get_action_adjacency(self):
        """Build adjacency list for state transitions."""
        adjacency = {}
        for action in self.action_ids:
            if action.state_from_id and action.state_to_id:
                if action.state_from_id not in adjacency:
                    adjacency[action.state_from_id] = []
                adjacency[action.state_from_id].append((action.state_to_id, action))
        return adjacency

    def _find_action_path_bfs(self, state_from, state_to, adjacency):
        """Find the shortest path of actions from state_from to state_to
        using BFS.

        Args:
            state_from (cx.tower.jet.state()): State to start from
            state_to (cx.tower.jet.state()): State to end at
            adjacency (dict): Adjacency list for state transitions
        """
        queue = [(state_from, [])]
        visited = {state_from}
        while queue:
            current_state, state_path = queue.pop(0)
            if current_state not in adjacency:
                continue
            for next_state, action in adjacency[current_state]:
                if next_state == state_to:
                    return state_path + [action]
                if next_state not in visited:
                    visited.add(next_state)
                    queue.append((next_state, state_path + [action]))
        return None

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   Install/Uninstall
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def _is_installation_needed(self, server):
        """Check if installation is needed for the given server.

        Args:
            server: Server to check

        Returns:
            bool: False if server is already installed or being installed,
                True otherwise
        """
        # Check if template is already installed on the server
        if server.id in self.server_ids.ids:
            return False

        # Check if template is already being installed on the server
        if (
            server.id
            in self.install_ids.filtered(
                lambda install: install.jet_template_install_id.state == "processing"
            ).server_id.ids
        ):
            return False

        return True

    def install_on_servers(self, servers):
        """Install the Jet Template on the selected servers.

        Args:
            servers (cx.tower.server()): Servers to install the Jet Template on
        """
        self.ensure_one()

        template_install_obj = self.env["cx.tower.jet.template.install"]
        now = fields.Datetime.now()
        context_timestamp = fields.Datetime.to_string(now)

        for server in servers:
            # Check if installation is needed for this server
            if not self._is_installation_needed(server):
                _logger.info(
                    "Template '%s' is already installed or being installed"
                    " on the server '%s'",
                    self.name,  # pylint: disable=no-member
                    server.name,
                )
                # Notify the user
                self.env.user.notify_info(
                    title=self.name,  # pylint: disable=no-member
                    message=_(
                        "%(timestamp)s<br/>Template is already installed "
                        "or being installed"
                        " on the server '%(server_name)s'",
                        timestamp=context_timestamp,
                        server_name=server.name,
                    ),
                )
                continue

            template_install_obj.install(
                template=self,
                server=server,
            )

        # Refresh the frontend views
        self.env.user.reload_views(model="cx.tower.jet.template", rec_ids=[self.id])

    def uninstall_from_servers(self, servers, raise_if_not_possible=True):
        """Uninstall the Jet Template from the selected servers.

        Args:
            servers (cx.tower.server()): Servers to uninstall the Jet Template from
            raise_if_not_possible (bool):
            If True, will raise an error if the uninstallation is not possible.
        """
        self.ensure_one()
        template_install_obj = self.env["cx.tower.jet.template.install"]

        for server in servers:
            # Check if installation is possible for this server
            warning_message = None
            # Template is not installed on the server
            if server.id not in self.server_ids.ids:
                warning_message = _(
                    "Template '%(template_name)s' is not installed "
                    "on the server '%(server_name)s'",
                    template_name=self.name,  # pylint: disable=no-member
                    server_name=server.name,
                )
            # There are still jets on the server
            elif server.jet_ids.filtered(lambda jet: jet.jet_template_id == self):
                warning_message = _(
                    "There are still jets of template '%(template_name)s' "
                    "on the server '%(server_name)s'",
                    template_name=self.name,  # pylint: disable=no-member
                    server_name=server.name,
                )
            # There are other templates that depend on this template
            # installed on the server
            elif server.jet_template_ids.filtered(
                lambda template: template.template_requires_ids.filtered(
                    lambda dependency: dependency.template_required_id == self
                )
            ):
                warning_message = _(
                    "There are other templates that depend "
                    "on template '%(template_name)s' "
                    "that are installed on the server '%(server_name)s'",
                    template_name=self.name,  # pylint: disable=no-member
                    server_name=server.name,
                )

            if warning_message:
                if raise_if_not_possible:
                    raise ValidationError(warning_message)
                self.env.user.notify_warning(
                    message=warning_message,
                    title=self.name,  # pylint: disable=no-member
                )
                continue

            template_install_obj.uninstall(
                template=self,
                server=server,
            )

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

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   Jet creation
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def create_jet(self, server, name=None, state=None, **kwargs):
        """
        Create a new jet from this template on the given server.

        Args:
            server (cx.tower.server()): The server to use
            name (str): The name of the jet.
                If not provided, a random name will be generated.
                Defaults to None.
            state (cx.tower.jet.state()): The state to set the jet to.
                If not provided, the jet will be created in the initial state.
                Defaults to None.
        Kwargs:
            field values to populate in the new jet record.
            NB: configuration variables are provided as follows:
            variable_values (dict): Custom configuration variables
                in the format of `{variable_reference: variable_value}`
                eg `{'odoo_version': '16.0'}`
        Returns:
            cx.tower.jet(): The new jet or False if the creation has failed
        """
        self.ensure_one()

        # Check if the jet creation is allowed on the given server
        if not self._allow_jet_creation(server):
            return False

        # Prepare the jet values
        vals = self._prepare_jet_values(server, name, **kwargs)

        # Create a new jet
        jet = self.env["cx.tower.jet"].create(vals)

        # Set the state of the jet
        if state:
            jet._bring_to_state(state)

        return jet

    def _prepare_jet_values(self, server, name=None, **kwargs):
        """
        Prepare the jet values to create a new jet based
        on the given server and template.

        Args:
            server (cx.tower.server()): The server to create the jet on
            **kwargs: Additional values to update in the final jet record.
        """
        self.ensure_one()

        # Check if the URL is valid
        url = kwargs.pop("url", None)
        if url and not is_valid_url(url, no_scheme_check=True):
            raise ValidationError(
                _(
                    "Invalid URL: '%(url)s'. URL must contain a protocol and "
                    "a proper domain or IP, eg 'https://my_tower_jet.example.com'",
                    url=url,
                )
            )

        # If no name is provided, generate a random one
        if not name:
            name = self._generate_jet_name()

        # Check if the same name already exists on the server
        # Keep generating a new name until a unique one is found
        jet_obj = self.env["cx.tower.jet"]
        # Pre-fetch existing names for this server
        existing_names = set(
            jet_obj.search([("server_id", "=", server.id)]).mapped("name")
        )

        for _attempt in range(MAX_JET_NAME_RETRIES):
            if name not in existing_names:
                break
            name = self._generate_jet_name()
        else:
            # Loop exhausted without finding unique name
            raise ValidationError(
                _(
                    "Failed to generate unique jet name after %(attempts)d attempts",
                    attempts=MAX_JET_NAME_RETRIES,
                )
            )

        # Prepare the Jet values
        vals = {
            "name": name,
            "jet_template_id": self.id,  # pylint: disable=no-member
            "server_id": server.id,
            "url": url,
        }

        # Parse specific fields from kwargs
        if kwargs:
            # Parse configuration variables
            configuration_variables = kwargs.pop("variable_values", {})
            if configuration_variables:
                variable_obj = self.env["cx.tower.variable"]
                variable_values = []
                for (
                    variable_reference,
                    variable_value,
                ) in configuration_variables.items():
                    variable = variable_obj.get_by_reference(variable_reference)
                    if variable:
                        variable_values.append(
                            (
                                0,
                                0,
                                {
                                    "variable_id": variable.id,
                                    "value_char": variable_value,
                                },
                            )
                        )
                        continue
                    _logger.warning(
                        "Variable reference '%s' not found while creating jet '%s'",
                        variable_reference,
                        self.name,  # pylint: disable=no-member
                    )

                if variable_values:
                    vals.update(
                        {
                            "variable_value_ids": variable_values,
                        }
                    )

        # Populate the allowed fields
        for field in self._allowed_jet_fields():
            if field in kwargs:
                vals[field] = kwargs.pop(field)

        return vals

    def _allowed_jet_fields(self):
        """Return the allowed fields for the jet creation"""
        self.ensure_one()
        return [
            "name",
            "reference",
            "sequence",
            "tag_ids",
            "partner_id",
            "jet_cloned_from_id",
            "scheduled_task_ids",
            "server_log_ids",
        ]

    def _allow_jet_creation(self, server):
        """
        Check if the jet creation is allowed on the given server.
        This function can be extended to check for other conditions.
        Eg if jet capacity is reached for the server.
        Or server template has a certain limit on the number of jets per server.

        Args:
            server (cx.tower.server()): The server to check

        Returns:
            bool: True if the jet creation is allowed, False otherwise
        """
        self.ensure_one()
        return True

    def _generate_jet_name(self):
        """Generate a unique name for a jet"""
        self.ensure_one()
        return (
            f"{self.name} "
            f"[{generate_random_id(sections=2, population=4, separator='-')}]"
        )

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   Dependency Graph
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def _build_dependency_graph(self):
        """Build a dependency graph of all templates this template depends on

        Returns:
            dict: A dictionary representing the dependency graph where:
                - Keys are template IDs
                - Values are dictionaries containing template info
                    and dependencies
        """
        self.ensure_one()

        graph = {}
        visited = set()

        # Use a stack to process templates iteratively instead of recursion
        stack = [self]

        while stack:
            template = stack.pop()

            # Skip if already visited
            if template.id in visited:
                continue

            # Mark as visited
            visited.add(template.id)

            # Add current template to graph
            graph[template.id] = {
                "template": template,
                "name": template.name,
                "reference": template.reference,
                "dependencies": [],
                "level": 0,  # Will be calculated later
            }

            # Add dependencies
            for dependency in template.template_requires_ids:
                required_template = dependency.template_required_id

                # Add dependency info
                dep_info = {
                    "template_id": required_template.id,
                    "template_name": required_template.name,
                    "template_reference": required_template.reference,
                    "required_state_id": dependency.state_required_id.id
                    if dependency.state_required_id
                    else None,
                    "required_state_name": dependency.state_required_id.name
                    if dependency.state_required_id
                    else None,
                }

                graph[template.id]["dependencies"].append(dep_info)

                # Add required template to stack if not yet visited
                if required_template.id not in visited:
                    stack.append(required_template)

        # Calculate dependency levels (distance from root template)
        self._calculate_dependency_levels(graph)

        return graph

    def _calculate_dependency_levels(self, graph):
        """Calculate the dependency level for each template in the graph

        Args:
            graph (dict): The dependency graph to update with levels
        """
        # Start with the root template (current template) at level 0
        queue = [(self.id, 0)]
        levels = {self.id: 0}

        while queue:
            template_id, level = queue.pop(0)

            if template_id not in graph:
                continue

            # Update the level in the graph
            graph[template_id]["level"] = level

            # Process dependencies
            for dep in graph[template_id]["dependencies"]:
                dep_template_id = dep["template_id"]
                new_level = level + 1

                # Only update if we haven't seen this template
                # or found a shorter path
                if dep_template_id not in levels or levels[dep_template_id] > new_level:
                    levels[dep_template_id] = new_level
                    queue.append((dep_template_id, new_level))

    def _topological_sort_dependency_graph(self, graph):
        """Topological order: prerequisite templates before dependents.

        For each edge ``required -> dependent`` (``dependent`` lists ``required``
        in ``template_requires_ids``), ``required`` appears earlier in the result.

        Tie-break: smallest template id first (deterministic).

        Args:
            graph (dict): Output of :meth:`_build_dependency_graph`.

        Returns:
            list: Template ids in topological order, or empty list if the graph
                has a cycle.
        """
        adj = defaultdict(list)
        indegree = {tid: 0 for tid in graph}

        for tid in graph:
            for dep in graph[tid]["dependencies"]:
                dep_id = dep["template_id"]
                if dep_id not in graph:
                    continue
                adj[dep_id].append(tid)
                indegree[tid] += 1

        heap = [tid for tid in graph if indegree[tid] == 0]
        heapq.heapify(heap)

        topo = []
        while heap:
            node = heapq.heappop(heap)
            topo.append(node)
            for succ in sorted(adj[node]):
                indegree[succ] -= 1
                if indegree[succ] == 0:
                    heapq.heappush(heap, succ)

        if len(topo) != len(graph):
            return []

        return topo

    def _get_all_dependencies_level_fallback(self, graph):
        """Fallback order when the dependency graph has a cycle: sort by level."""
        dependencies_with_levels = []
        for template_id, info in graph.items():
            if template_id != self.id:
                dependencies_with_levels.append((info["template"], info["level"]))

        dependencies_with_levels.sort(key=lambda x: x[1])
        return [t for t, _level in dependencies_with_levels]

    def _get_all_dependencies(self):
        """Get all templates that this template depends on (directly or indirectly).

        Order is **reverse topological**
        (see :meth:`_topological_sort_dependency_graph`):
        ``cx.tower.jet.template.install`` assigns increasing ``order`` and runs
        tasks with highest ``order`` first, so prerequisites must appear **later**
        in this list than templates that depend on them.

        Returns:
            list: ``cx.tower.jet.template`` records excluding ``self``.
        """
        self.ensure_one()
        graph = self._build_dependency_graph()

        topo_order = self._topological_sort_dependency_graph(graph)
        if not topo_order:
            _logger.warning(
                "Dependency cycle or invalid graph for template %s; "
                "using level-based dependency order",
                self.name,
            )
            return self._get_all_dependencies_level_fallback(graph)

        dependencies = []
        for tid in reversed(topo_order):
            if tid == self.id:
                continue
            dependencies.append(graph[tid]["template"])

        return dependencies

    def _check_dependency_satisfaction(self, server):
        """Check if all dependant templates are installed on the server.

        Args:
            server (cx.tower.server()): Server to check dependencies for

        Returns:
            list: Templates that are not installed on the server
        """
        dependencies = self._get_all_dependencies()

        missing_templates = []

        for dependency in dependencies:
            if server and server.id not in dependency.server_ids.ids:
                missing_templates.append(dependency)

        return missing_templates

    def _get_all_depend_on_this(self):
        """Get all templates that depend on this template (directly or indirectly)

        Returns:
            recordset: All templates that depend on this template
        """
        self.ensure_one()

        # Find all templates that have this template as a dependency
        dependent_templates = set()

        # Start with direct dependents
        direct_dependents = self.env["cx.tower.jet.template"].search(
            [("template_requires_ids.template_required_id", "=", self.id)]
        )

        # Use a queue to find indirect dependents
        queue = list(direct_dependents)
        processed = set()

        while queue:
            current_template = queue.pop(0)

            if current_template.id in processed:
                continue

            processed.add(current_template.id)
            dependent_templates.add(current_template.id)

            # Find templates that depend on the current template
            next_level_dependents = self.env["cx.tower.jet.template"].search(
                [
                    (
                        "template_requires_ids.template_required_id",
                        "=",
                        current_template.id,
                    )
                ]
            )

            for template in next_level_dependents:
                if template.id not in processed:
                    queue.append(template)

        return self.env["cx.tower.jet.template"].browse(list(dependent_templates))

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   SVG Graph Generation
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def _generate_svg_graph(self, graph_data):
        """Generate SVG dependency graph

        Args:
            graph_data (dict): Dictionary containing template dependency information

        Returns:
            bytes: Base64 encoded SVG content
        """
        width, height = 800, 600

        # Create SVG root
        svg = ET.Element(
            "svg",
            {
                "width": str(width),
                "height": str(height),
                "xmlns": "http://www.w3.org/2000/svg",
                "viewBox": f"0 0 {width} {height}",
            },
        )

        # Add styles
        style = ET.SubElement(svg, "style")
        style.text = """
            .node { stroke: #333; stroke-width: 2; }
            .edge { stroke: #666; stroke-width: 2; marker-end: url(#arrowhead); }
            .text { font-family: Arial; font-size: 14px; text-anchor: middle; font-weight: bold; }
            .edge-label { font-family: Arial; font-size: 12px; text-anchor: middle; fill: #444; }
            .root-node { fill: lightblue; }
            .direct-dep { fill: lightgreen; }
            .indirect-dep { fill: lightyellow; }
        """  # noqa: E501

        # Add arrow marker
        defs = ET.SubElement(svg, "defs")
        marker = ET.SubElement(
            defs,
            "marker",
            {
                "id": "arrowhead",
                "markerWidth": "10",
                "markerHeight": "7",
                "refX": "9",
                "refY": "3.5",
                "orient": "auto",
            },
        )
        ET.SubElement(marker, "polygon", {"points": "0 0, 10 3.5, 0 7", "fill": "#666"})

        if not graph_data or len(graph_data) <= 1:
            # Single node
            self._add_single_node_svg(svg, width, height)
        else:
            # Multiple nodes - arrange in levels
            self._add_multi_node_svg(svg, graph_data, width, height)

        # Convert to string and then to base64
        svg_string = ET.tostring(svg, encoding="unicode")
        return base64.b64encode(svg_string.encode("utf-8"))

    def _add_single_node_svg(self, svg, width, height):
        """Add a single node to the SVG for templates with no dependencies

        Args:
            svg (xml.etree.ElementTree.Element): SVG root element
            width (int): SVG width
            height (int): SVG height
        """
        node_width, node_height = 200, 60
        x = width // 2 - node_width // 2
        y = height // 2 - node_height // 2

        # Draw node rectangle
        ET.SubElement(
            svg,
            "rect",
            {
                "x": str(x),
                "y": str(y),
                "width": str(node_width),
                "height": str(node_height),
                "class": "node root-node",
                "rx": "10",  # Rounded corners
            },
        )

        # Add text
        ET.SubElement(
            svg,
            "text",
            {"x": str(width // 2), "y": str(height // 2 + 5), "class": "text"},
        ).text = self.name

    def _add_multi_node_svg(self, svg, graph_data, width, height):
        """Add multiple nodes and edges to the SVG for complex dependency graphs

        Args:
            svg (xml.etree.ElementTree.Element): SVG root element
            graph_data (dict): Dictionary containing template dependency information
            width (int): SVG width
            height (int): SVG height
        """
        # Group templates by level
        levels = {}
        for template_id, info in graph_data.items():
            level = info["level"]
            if level not in levels:
                levels[level] = []
            levels[level].append((template_id, info))

        positions = {}
        node_width = 180
        node_height = 60
        level_height = 120
        margin = 50

        # Calculate positions for each node
        for level, nodes in levels.items():
            y = margin + level * level_height
            available_width = width - 2 * margin

            if len(nodes) == 1:
                # Center single node
                x = width // 2
                positions[nodes[0][0]] = (x, y)
            else:
                # Distribute multiple nodes
                spacing = available_width / len(nodes)
                for i, node_tuple in enumerate(nodes):
                    template_id = node_tuple[0]  # Extract template_id from tuple
                    x = margin + spacing * (i + 0.5)
                    positions[template_id] = (x, y)

        # Draw edges first (so they appear behind nodes)
        self._draw_svg_edges(svg, graph_data, positions, node_height)

        # Draw nodes
        self._draw_svg_nodes(svg, graph_data, positions, node_width, node_height)

    def _draw_svg_edges(self, svg, graph_data, positions, node_height):
        """Draw edges between nodes in the SVG

        Args:
            svg (xml.etree.ElementTree.Element): SVG root element
            graph_data (dict): Dictionary containing template dependency information
            positions (dict): Dictionary mapping template IDs to (x, y) positions
            node_height (int): Height of nodes for edge positioning
        """
        for template_id, info in graph_data.items():
            if template_id in positions:
                x1, y1 = positions[template_id]

                for dep in info["dependencies"]:
                    dep_id = dep["template_id"]
                    if dep_id in positions:
                        x2, y2 = positions[dep_id]

                        # Draw edge line
                        ET.SubElement(
                            svg,
                            "line",
                            {
                                "x1": str(x1),
                                "y1": str(y1 + node_height // 2),
                                "x2": str(x2),
                                "y2": str(y2 - node_height // 2),
                                "class": "edge",
                            },
                        )

                        # Add edge label if there's a required state
                        if dep["required_state_name"]:
                            mid_x = (x1 + x2) / 2
                            mid_y = (y1 + y2) / 2

                            # Background rectangle for label
                            label_text = dep["required_state_name"]
                            label_width = len(label_text) * 8 + 10
                            label_height = 20

                            ET.SubElement(
                                svg,
                                "rect",
                                {
                                    "x": str(mid_x - label_width // 2),
                                    "y": str(mid_y - label_height // 2),
                                    "width": str(label_width),
                                    "height": str(label_height),
                                    "fill": "white",
                                    "stroke": "#ccc",
                                    "rx": "3",
                                },
                            )

                            ET.SubElement(
                                svg,
                                "text",
                                {
                                    "x": str(mid_x),
                                    "y": str(mid_y + 4),
                                    "class": "edge-label",
                                },
                            ).text = label_text

    def _draw_svg_nodes(self, svg, graph_data, positions, node_width, node_height):
        """Draw nodes in the SVG

        Args:
            svg (xml.etree.ElementTree.Element): SVG root element
            graph_data (dict): Dictionary containing template dependency information
            positions (dict): Dictionary mapping template IDs to (x, y) positions
            node_width (int): Width of nodes
            node_height (int): Height of nodes
        """
        for template_id, info in graph_data.items():
            if template_id in positions:
                x, y = positions[template_id]
                template_obj = info["template"]

                # Determine node class based on level
                if info["level"] == 0:
                    node_class = "node root-node"
                elif info["level"] == 1:
                    node_class = "node direct-dep"
                else:
                    node_class = "node indirect-dep"

                # Draw node rectangle
                ET.SubElement(
                    svg,
                    "rect",
                    {
                        "x": str(x - node_width // 2),
                        "y": str(y - node_height // 2),
                        "width": str(node_width),
                        "height": str(node_height),
                        "class": node_class,
                        "rx": "10",  # Rounded corners
                    },
                )

                # Add text (truncate if too long)
                display_name = template_obj.name
                if len(display_name) > 20:
                    display_name = display_name[:17] + "..."

                ET.SubElement(
                    svg, "text", {"x": str(x), "y": str(y + 5), "class": "text"}
                ).text = display_name

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   Access role mixin functions
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def _get_post_create_fields(self):
        """
        Add fields that should be populated after jet template creation
        """
        res = super()._get_post_create_fields()
        return res + ["variable_value_ids", "server_log_ids"]
