# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CxTowerJetTemplateDependency(models.Model):
    """Define dependencies between Jet templates"""

    _name = "cx.tower.jet.template.dependency"
    _inherit = "cx.tower.reference.mixin"
    _description = "Cetmix Tower Jet Template Dependency"
    _log_access = False

    name = fields.Char(related="template_id.name", readonly=True)
    template_id = fields.Many2one(
        string="Jet",
        comodel_name="cx.tower.jet.template",
        ondelete="cascade",
        required=True,
        help="The Jet template that requires another template",
    )

    template_required_id = fields.Many2one(
        string="Required Jet",
        comodel_name="cx.tower.jet.template",
        ondelete="restrict",
        required=True,
        help="The Jet template that is required to be in a specific state",
        domain="[('id', '!=', template_id)]",
    )

    state_required_id = fields.Many2one(
        string="Required State",
        comodel_name="cx.tower.jet.state",
        required=True,
        ondelete="restrict",
        help="The state of the required Jet",
    )

    _sql_constraints = [
        (
            "unique_template_dependency",
            "UNIQUE(template_id, template_required_id)",
            "A template can only depend on another template once!",
        ),
    ]

    @api.constrains(
        "template_id",
        "template_required_id",
    )
    def _check_circular_dependency(self):
        """Check if this dependency would create a circular dependency chain"""
        for dependency in self:
            # Skip if the dependency isn't properly set yet
            if not dependency.template_id or not dependency.template_required_id:
                continue

            # Self-dependency is not allowed and already prevented by domain constraints
            if dependency.template_id == dependency.template_required_id:
                raise ValidationError(_("A template cannot depend on itself!"))

            # Build dependency graph
            graph = self._build_dependency_graph()

            # Add the new dependency edge being created
            if dependency.template_id.id not in graph:
                graph[dependency.template_id.id] = set()
            graph[dependency.template_id.id].add(dependency.template_required_id.id)

            # Check for circular dependencies
            if self._has_cycle(graph, dependency.template_id.id):
                raise ValidationError(
                    _(
                        "This dependency would create a circular reference chain! "
                        "Template '%(template)s' would indirectly depend on itself.",
                        template=dependency.template_id.name,
                    )
                )

    @api.depends("template_id", "template_required_id")
    def _compute_display_name(self):
        for dependency in self:
            dependency.display_name = (
                (
                    f"{dependency.template_id.name} ->"
                    f" {dependency.template_required_id.name}"
                )
                if dependency.template_id and dependency.template_required_id
                else "..."
            )

    def write(self, vals):
        """Do not allow modifications after creation"""
        # Allow modifications in install mode only to load demo data
        if ("template_id" in vals or "template_required_id" in vals) and not (
            self._context.get("install_mode") and self._context.get("install_xmlid")
        ):
            raise ValidationError(
                _(
                    "You cannot modify an existing template dependency! "
                    "Please remove it and create a new one."
                )
            )
        return super().write(vals)

    def _build_dependency_graph(self):
        """Build a directed graph of template dependencies

        Returns:
            dict: A dictionary where keys are template IDs and values are
                 sets of template IDs that are required by the key template
        """
        graph = {}
        # Get all dependencies in the system
        # TODO: This is not efficient, we should find a better way later.
        # Eg cache the graph in the template model.
        all_deps = self.search([])

        for dep in all_deps:
            from_id = dep.template_id.id
            to_id = dep.template_required_id.id

            if from_id not in graph:
                graph[from_id] = set()

            graph[from_id].add(to_id)

            # Ensure the to_id is in the graph even if it doesn't require anything
            if to_id not in graph:
                graph[to_id] = set()

        return graph

    def _has_cycle(self, graph, start_node, visited=None, path=None):
        """Check if the graph has a cycle starting from start_node

        Args:
            graph (dict): Dependency graph where keys are template IDs and values are
                          sets of template IDs that the key depends on
            start_node (int): Template ID to start the traversal from
            visited (set, optional): Set of already visited nodes
            path (set, optional): Set of nodes in the current DFS path

        Returns:
            bool: True if a cycle is detected, False otherwise
        """
        if visited is None:
            visited = set()
        if path is None:
            path = set()

        visited.add(start_node)
        path.add(start_node)

        for neighbor in graph.get(start_node, set()):
            if neighbor not in visited:
                if self._has_cycle(graph, neighbor, visited, path):
                    return True
            elif neighbor in path:
                # We found a cycle
                return True

        # Remove the current node from the path as we backtrack
        path.remove(start_node)
        return False
