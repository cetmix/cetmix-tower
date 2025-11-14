# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import ast
import base64
import logging
import xml.etree.ElementTree as ET

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .tools import generate_random_id

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

    active = fields.Boolean(default=True)
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
    jet_count = fields.Integer(
        compute="_compute_jet_count",
    )
    show_in_wizard = fields.Boolean(
        string="Show in Wizard",
        help="If enabled, the template will be shown in the wizard to create a new jet",
    )

    # Servers
    server_ids = fields.Many2many(
        comodel_name="cx.tower.server",
        relation="cx_tower_jet_template_server_rel",
        column1="jet_template_id",
        column2="server_id",
        string="Installed on Servers",
        readonly=False,
        help="These servers have this jet template installed",
        copy=False,
    )
    limit_per_server = fields.Integer(
        string="Limit per Server",
        help="Maximum number of Jets that can be launched on a server. "
        "Set to 0 for unlimited.",
    )
    file_ids = fields.One2many(
        comodel_name="cx.tower.file",
        inverse_name="jet_template_id",
        string="Files",
        help="Files of this jet template",
        copy=False,
    )

    # Flight Plans
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
    )
    template_required_by_ids = fields.One2many(
        comodel_name="cx.tower.jet.template.dependency",
        inverse_name="template_required_id",
        string="Required by",
        help="Define other templates that require this template"
        " to be in a specific"
        " state to function",
    )

    # Installation
    install_ids = fields.One2many(
        comodel_name="cx.tower.jet.template.install.line",
        inverse_name="jet_template_id",
        string="Installations",
        help="Installations of the template",
        auto_join=True,
        copy=False,
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
        help="SVG image content of the dependency" " graph of the template",
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
                )
                # Take the first one
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
                )
                # Take the first one
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
                template.dependency_graph_image = False

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
            "name": "Install on Servers",
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
            server_id = self.env.context.get("default_server_id")
            server = self.env["cx.tower.server"].browse(server_id)
        if not server:
            raise ValidationError(_("No server selected"))

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
                lambda install: install.state in ["processing", "to_install"]
            ).server_id.ids
        ):
            return False

        return True

    def install_on_servers(self, servers):
        """Install the Jet Template on the selected servers.

        Args:
            servers (cx.tower.server()): Servers to install the Jet Template on
            installed_by_template (cx.tower.jet.template()): Template that is
                installing this one. This happens when a template is installing
                its dependencies.
        """
        self.ensure_one()

        template_install_obj = self.env["cx.tower.jet.template.install"]

        for server in servers:
            # Check if installation is needed for this server
            if not self._is_installation_needed(server):
                _logger.info(
                    "Template '%s' is already installed or being installed"
                    " on the server '%s'",
                    self.name,  # pylint: disable=no-member
                    server.name,
                )
                continue

            template_install_obj.install(
                template=self,
                server=server,
            )

    def uninstall_from_servers(self, servers):
        """Uninstall the Jet Template from the selected servers.

        Args:
            servers (cx.tower.server()): Servers to uninstall"
            " the Jet Template from
        """
        self.ensure_one()
        # TODO: Implement the uninstallation
        raise UserError(
            _(
                "Uninstallation is not implemented yet. "
                "Please remove the template from the servers manually."
            )
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

    def create_jet(self, server, name=None, **kwargs):
        """
        Create a new jet from this template on the given server.

        Args:
            server (cx.tower.server()): The server to use
            name (str): The name of the jet
        Kwargs:
            configuration_variables (dict): Custom configuration variables
                Following format is used:
                    `variable_reference`: `variable_value_char`
                    eg:
                    {'branch': 'prod', 'odoo_version': '16.0'}
        Returns:
            cx.tower.jet(): The new jet or False if the creation has failed
        """
        self.ensure_one()

        # Check if the jet creation is allowed on the given server
        if not self._allow_jet_creation(server):
            return False

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
                _("Failed to generate unique jet name after %d attempts")
                % MAX_JET_NAME_RETRIES
            )

        # Prepare the Jet values
        vals = {
            "name": name,
            "jet_template_id": self.id,  # pylint: disable=no-member
            "server_id": server.id,
        }

        # Parse kwargs
        if kwargs:
            # Parse configuration variables
            configuration_variables = kwargs.get("configuration_variables", {})
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

                if variable_values:
                    vals.update(
                        {
                            "variable_value_ids": variable_values,
                        }
                    )
                else:
                    _logger.warning(
                        "Variable reference '%s' not found when creating jet '%s'",
                        variable_reference,
                        name,
                    )

        # Create a new jet
        jet = self.env["cx.tower.jet"].create(vals)
        return jet

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

    def _get_all_dependencies(self):
        """Get all templates that this template depends on (directly or indirectly)
        ordered by dependency level

        Returns:
            list: All templates that this template depends on, ordered by level
        """
        graph = self._build_dependency_graph()
        dependencies = []

        # Build list of (template_id, level) tuples, excluding self
        dependencies_with_levels = []
        for template_id, info in graph.items():
            if template_id != self.id:
                dependencies_with_levels.append((info["template"], info["level"]))

        # Sort by level (closest dependencies first)
        dependencies_with_levels.sort(key=lambda x: x[1])

        # Extract just the template IDs in the correct order
        for dependency in dependencies_with_levels:
            dependencies.append(dependency[0])

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
