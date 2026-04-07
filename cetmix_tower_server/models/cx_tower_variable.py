# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import logging
import uuid
from urllib.parse import urlparse

from odoo import api, fields, models
from odoo.tools import LazyTranslate
from odoo.tools.safe_eval import safe_eval, wrap_module

_lt = LazyTranslate(__name__, default_lang="en_US")


_logger = logging.getLogger(__name__)

re = wrap_module(
    __import__("re"),
    [
        "match",
        "fullmatch",
        "search",
        "sub",
        "subn",
        "split",
        "findall",
        "finditer",
        "compile",
        "template",
        "escape",
        "error",
    ],
)

# Maximum recursion depth for variable value rendering
# to prevent infinite loops
MAX_DEPTH = 10


class TowerVariable(models.Model):
    """Variables"""

    _name = "cx.tower.variable"
    _description = "Cetmix Tower Variable"
    _inherit = [
        "cx.tower.reference.mixin",
        "cx.tower.access.mixin",
        "cx.tower.tag.mixin",
    ]

    _order = "name"

    DEFAULT_VALIDATION_MESSAGE = _lt("Invalid value!")
    SYSTEM_VARIABLE_REFERENCE = "tower"

    value_ids = fields.One2many(
        string="Values",
        comodel_name="cx.tower.variable.value",
        inverse_name="variable_id",
    )
    value_ids_count = fields.Integer(
        string="Value Count", compute="_compute_variable_counters"
    )
    option_ids = fields.One2many(
        comodel_name="cx.tower.variable.option",
        inverse_name="variable_id",
        string="Options",
        auto_join=True,
    )
    variable_type = fields.Selection(
        selection=[("s", "String"), ("o", "Options")],
        default="s",
        required=True,
        string="Type",
    )
    applied_expression = fields.Text(
        help="Python expression to apply to the variable value. \n"
        "You can use general python sting functions and 're' module "
        "for regex operations. "
        "Use 'value' variable to refer to the variable value, use 'result'"
        " to assign the final result that will be used as a variable value.\n"
        "Eg 'result = value.lower().replace(' ', '_')'",
    )
    validation_pattern = fields.Char(
        help="Regex pattern to validate the variable values using the "
        "'re.match' function. Eg. ^[a-z0-9]+$ \n"
        "If empty, the variable values will not be validated.",
    )
    validation_message = fields.Char(
        translate=True,
        help="Message to display when the variable value is invalid. \n"
        "First line will be added automatically: "
        "`Variable:<variable_name>, Value: <value>`\n"
        "Eg: `Variable: Customer Name, Value: Test\nInvalid value!`\n"
        "If empty, the default message will be used.",
    )
    note = fields.Text(
        help="Additional notes about the variable. \n"
        "This field will be displayed in the variable form.",
    )

    # --- Link to records where the variable is used
    command_ids = fields.Many2many(
        comodel_name="cx.tower.command",
        relation="cx_tower_command_variable_rel",
        column1="variable_id",
        column2="command_id",
        copy=False,
    )
    command_ids_count = fields.Integer(
        string="Command Count", compute="_compute_variable_counters"
    )
    plan_line_ids = fields.Many2many(
        comodel_name="cx.tower.plan.line",
        relation="cx_tower_plan_line_variable_rel",
        column1="variable_id",
        column2="plan_line_id",
        copy=False,
    )
    plan_line_ids_count = fields.Integer(
        string="Plan Line Count", compute="_compute_variable_counters"
    )
    file_ids = fields.Many2many(
        comodel_name="cx.tower.file",
        relation="cx_tower_file_variable_rel",
        column1="variable_id",
        column2="file_id",
        copy=False,
    )
    file_ids_count = fields.Integer(
        string="File Count", compute="_compute_variable_counters"
    )
    file_template_ids = fields.Many2many(
        comodel_name="cx.tower.file.template",
        relation="cx_tower_file_template_variable_rel",
        column1="variable_id",
        column2="file_template_id",
        copy=False,
    )
    file_template_ids_count = fields.Integer(
        string="File Template Count", compute="_compute_variable_counters"
    )
    variable_value_ids = fields.Many2many(
        comodel_name="cx.tower.variable.value",
        relation="cx_tower_variable_value_variable_rel",
        column1="variable_id",
        column2="variable_value_id",
        copy=False,
    )
    variable_value_ids_count = fields.Integer(
        string="Variable Value Count", compute="_compute_variable_counters"
    )

    _sql_constraints = [("name_uniq", "unique (name)", "Variable names must be unique")]

    def _compute_variable_counters(self):
        """Count number of variable values for the variable"""
        for rec in self:
            rec.update(
                {
                    "variable_value_ids_count": len(rec.variable_value_ids),
                    "command_ids_count": len(rec.command_ids),
                    "plan_line_ids_count": len(rec.plan_line_ids),
                    "file_ids_count": len(rec.file_ids),
                    "file_template_ids_count": len(rec.file_template_ids),
                    "value_ids_count": len(rec.value_ids),
                }
            )

    def action_open_values(self):
        """Open the variable values"""
        self.ensure_one()
        context = self.env.context.copy()
        context.update(
            {
                "default_variable_id": self.id,
            }
        )

        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Variable Values"),
            "res_model": "cx.tower.variable.value",
            "views": [[False, "list"]],
            "target": "current",
            "context": context,
            "domain": [("variable_id", "=", self.id)],
        }

    def action_open_commands(self):
        """Open the commands where the variable is used"""

        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_command"
        )
        action.update(
            {
                "domain": [("variable_ids", "in", self.ids)],
            }
        )
        return action

    def action_open_plan_lines(self):
        """Open the plan lines where the variable is used"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Plan Lines"),
            "res_model": "cx.tower.plan.line",
            "views": [
                [False, "tree"],
                [
                    self.env.ref("cetmix_tower_server.cx_tower_plan_line_view_form").id,
                    "form",
                ],
            ],
            "target": "current",
            "domain": [("variable_ids", "in", self.ids)],
        }

    def action_open_files(self):
        """Open the files where the variable is used"""
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "cetmix_tower_server.cx_tower_file_action"
        )
        action.update(
            {
                "domain": [("variable_ids", "in", self.ids)],
            }
        )
        return action

    def action_open_file_templates(self):
        """Open the file templates where the variable is used"""
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "cetmix_tower_server.cx_tower_file_template_action"
        )
        action.update(
            {
                "domain": [("variable_ids", "in", self.ids)],
            }
        )
        return action

    def action_open_variable_values(self):
        """Open the variable values where the variable is used"""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Variable Values"),
            "res_model": "cx.tower.variable.value",
            "views": [[False, "list"]],
            "target": "current",
            "domain": [("variable_ids", "in", self.ids)],
        }

    @api.model
    def _get_eval_context(self, value_char=None):
        """
        Evaluation context to pass to safe_eval to evaluate
        the Python expression used in the `applied_expression` field

        Args:
            value_char (Char): variable value

        Returns:
            dict: evaluation context
        """
        return {
            "re": re,
            "value": value_char,
        }

    #  Reference rename propagation

    def write(self, vals):
        """Override the write method to propagate variable reference updates.

        Records the old reference values, performs the write, and if the reference
        field has changed, initiates propagation to update related records.
        """
        old_refs = (
            {rec.id: rec.reference for rec in self} if "reference" in vals else {}
        )
        res = super().write(vals)
        if "reference" in vals:
            for rec in self:
                old_ref = old_refs.get(rec.id)
                if old_ref and old_ref != rec.reference:
                    rec._propagate_reference_change(old_ref, rec.reference)
        return res

    def _propagate_reference_change(self, old_ref, new_ref):
        """Replace all occurrences of an old variable reference with a new one.

        Compiles a pattern matching the old Jinja-style reference, then searches across
        configured models and fields to substitute any matches, preserving formatting.
        """
        pattern = re.compile(r"(\{\{\s*)" + re.escape(old_ref) + r"(\s*\}\})")

        def _replace(text):
            """Helper to replace old_ref with new_ref in the given text."""
            return pattern.sub(lambda m: f"{m.group(1)}{new_ref}{m.group(2)}", text)

        model_fields_map = self._get_propagation_field_mapping()

        for model_name, field_names in model_fields_map.items():
            Model = self.env[model_name]

            if model_name == "cx.tower.variable.value":
                domain = [("variable_id", "=", self.id)]
            else:
                domain = [("variable_ids", "in", self.ids)]

            for record in Model.search(domain):
                vals = {}
                for field_name in field_names:
                    value = record[field_name]
                    if isinstance(value, str) and old_ref in value:
                        new_value = _replace(value)
                        if new_value != value:
                            vals[field_name] = new_value

                if vals:
                    record.with_context(skip_reference_propagation=True).write(vals)
                    _logger.debug(
                        "Variable reference updated in %s(%s): %s",
                        model_name,
                        record.id,
                        ", ".join(vals.keys()),
                    )

    def _get_propagation_field_mapping(self):
        """Return the mapping of models to fields for reference change propagation.

        The returned dict maps each model name to a list of field names
        that may contain variable references requiring updates.
        """
        return {
            "cx.tower.command": ["code", "path"],
            "cx.tower.file": ["code", "server_dir", "name"],
            "cx.tower.file.template": ["code", "server_dir", "file_name"],
            "cx.tower.variable.value": ["value_char"],
            "cx.tower.plan.line": ["condition"],
        }

    def _get_dependent_model_relation_fields(self):
        """Check cx.tower.reference.mixin for the function documentation"""
        res = super()._get_dependent_model_relation_fields()
        return res + ["value_ids"]

    def _validate_value(self, value_char=None):
        """
        Validate the variable value

        Args:
            value_char (Char): variable value

        Returns:
            (Boolean, Char): (is_valid, validation_message)
        """
        self.ensure_one()
        if (
            not self.validation_pattern
            or not value_char
            or re.match(self.validation_pattern, value_char)  # pylint: disable=no-member
        ):
            return True, None
        message = self.validation_message or self.DEFAULT_VALIDATION_MESSAGE
        return (
            False,
            self.env._(
                "Variable: %(var)s, Value: %(val)s\n%(msg)s",
                msg=message,
                var=self.name,  # pylint: disable=no-member
                val=value_char,
            ),
        )

    # ------------------------------
    # ---- Managing variable values
    # ------------------------------
    def _get_value(
        self,
        server=None,
        server_template=None,
        plan_line_action=None,
        jet_template=None,
        jet=None,
    ):
        """Get the value of the variable.

        0. No arguments: return the global value.
        1. Server Template: return the Server Template specific value
            or the global value.
        2. Server: return the Server specific value or the global value.
        3. Jet Template: return the Jet Template specific value
            or the Server value
            or the global value.
        4. Jet: return the Jet specific value
            or the Jet Template value
            or the Server value
            or the global value.
        5. Plan Line Action: return the Plan Line Action specific value.

        Args:
            server (cx.tower.server): Server
            server_template (cx.tower.server.template): Server Template
            plan_line_action (cx.tower.plan.line.action): Plan Line Action
            jet_template (cx.tower.jet.template): Jet Template
            jet (cx.tower.jet): Jet

        Returns:
            Char: The value of the variable or None if no value is found.
        """
        self.ensure_one()
        values = self.value_ids

        # 0. Set server and jet template from jet
        # if jet is provided
        if jet:
            server = jet.server_id
            jet_template = jet.jet_template_id

        # 1. Prepare the values

        # Initialize all values to None
        global_value_char = server_value_char = server_template_value_char = (
            plan_line_action_value_char
        ) = jet_template_value_char = jet_value_char = None

        # Get origin id's in case we are dealing with onchange()
        server_id = (
            server._origin.id
            if server and hasattr(server, "_origin")
            else server.id
            if server
            else None
        )
        server_template_id = (
            server_template._origin.id
            if server_template and hasattr(server_template, "_origin")
            else server_template.id
            if server_template
            else None
        )
        plan_line_action_id = (
            plan_line_action._origin.id
            if plan_line_action and hasattr(plan_line_action, "_origin")
            else plan_line_action.id
            if plan_line_action
            else None
        )
        jet_template_id = (
            jet_template._origin.id
            if jet_template and hasattr(jet_template, "_origin")
            else jet_template.id
            if jet_template
            else None
        )
        jet_id = (
            jet._origin.id
            if jet and hasattr(jet, "_origin")
            else jet.id
            if jet
            else None
        )

        # Check all values for the variable and assign them.
        # Note: we are not using filtered() to avoid multiple iterations
        # on the same recordset.
        for variable_value in values:
            # Fetch the server value
            if (
                server
                and server_value_char is None
                and variable_value.server_id.id == server_id
            ):
                server_value_char = variable_value.value_char
                continue
            # Fetch the server template value
            if (
                server_template
                and server_template_value_char is None
                and variable_value.server_template_id.id == server_template_id
            ):
                server_template_value_char = variable_value.value_char
                continue
            # Fetch the plan line action value
            if (
                plan_line_action
                and plan_line_action_value_char is None
                and variable_value.plan_line_action_id.id == plan_line_action_id
            ):
                plan_line_action_value_char = variable_value.value_char
                continue
            # Fetch the jet template value
            if (
                jet_template
                and jet_template_value_char is None
                and variable_value.jet_template_id.id == jet_template_id
            ):
                jet_template_value_char = variable_value.value_char
                continue
            # Fetch the jet value
            if jet and jet_value_char is None and variable_value.jet_id.id == jet_id:
                jet_value_char = variable_value.value_char
                continue
            # Fetch the global value
            if global_value_char is None and variable_value.is_global:
                global_value_char = variable_value.value_char

        # 2. Compose the response
        # 2.1. Server Template
        if server_template:
            return server_template_value_char or global_value_char

        # 2.2. Jet
        if jet:
            return (
                jet_value_char
                if jet_value_char is not None
                else jet_template_value_char
                if jet_template_value_char is not None
                else server_value_char
                if server_value_char is not None
                else global_value_char
            )

        # 2.3. Jet Template
        if jet_template:
            return (
                jet_template_value_char
                if jet_template_value_char is not None
                else server_value_char
                if server_value_char is not None
                else global_value_char
            )

        # 2.4. Server
        if server:
            return (
                server_value_char
                if server_value_char is not None
                else global_value_char
            )

        # 2.5. Plan Line Action
        if plan_line_action:
            return plan_line_action_value_char

        # 2.6. Global
        return global_value_char

    @api.model
    def _get_variable_values_by_references(
        self,
        variable_references,
        apply_modifiers=True,
        **kwargs,
    ):
        """Get variable values for multiple references.
        This method is designed to be used for template rendering.
        It also includes system variable values in the result.

        Args:
            variable_references (list of Char): variable names
            apply_modifiers (bool): apply Python modifiers to the values
            **kwargs: keyword arguments to pass to the _get_value method
            - server (cx.tower.server): Server
            - server_template (cx.tower.server.template): Server Template
            - plan_line_action (cx.tower.plan.line.action): Plan Line Action
            - jet_template (cx.tower.jet.template): Jet Template
            - jet (cx.tower.jet): Jet
            - _depth (int): Depth of the recursion
        Returns:
            dict {variable_reference: value}
        """
        # 0. Get keyword arguments
        server = kwargs.get("server")
        server_template = kwargs.get("server_template")
        plan_line_action = kwargs.get("plan_line_action")
        jet_template = kwargs.get("jet_template")
        jet = kwargs.get("jet")
        _depth = kwargs.get("_depth", 0)

        # 0. Update server and jet template from jet
        if jet:
            server = jet.server_id
            jet_template = jet.jet_template_id

        # 1. Get system variable values
        variable_values = {}
        system_vars = self._get_system_variable_values(
            server=server, jet_template=jet_template, jet=jet
        )
        if system_vars:
            variable_values[self.SYSTEM_VARIABLE_REFERENCE] = system_vars

        # Return just system variable values if no references are provided
        # or the only one is the system variable
        # Need a fallback in case system variable is provides several times
        if not variable_references or (
            all(
                reference == self.SYSTEM_VARIABLE_REFERENCE
                for reference in variable_references
            )
        ):
            return variable_values

        # 2. Get variable value records
        for reference in variable_references:
            # Do not overwrite system variable values
            if reference == self.SYSTEM_VARIABLE_REFERENCE:
                continue
            variable = self.get_by_reference(reference)  # pylint: disable=no-member

            # Assign the value to the variable values dictionary
            variable_value = (
                variable._get_value(
                    server=server,
                    server_template=server_template,
                    plan_line_action=plan_line_action,
                    jet_template=jet_template,
                    jet=jet,
                )
                if variable
                else None
            )
            variable_values[reference] = variable_value

        # 3. Render templates in values
        self._render_variable_values(
            variable_values,
            server=server,
            jet_template=jet_template,
            jet=jet,
            _depth=_depth,
        )

        # 4. Apply modifiers
        if apply_modifiers:
            self._apply_modifiers(variable_values)

        return variable_values

    def _render_variable_values(self, variable_values, **kwargs):
        """Renders variable values using other variable values.
        For example we have the following values:
            "server_root": "/opt/server"
            "server_assets": "{{ server_root }}/assets"

        This function will render the "server_assets" variable:
            "server_assets": "/opt/server/assets"

        Args:
            variable_values (dict): variable values to complete
            **kwargs: keyword arguments to pass to the _get_value method
            - server (cx.tower.server): Server
            - server_template (cx.tower.server.template): Server Template
            - plan_line_action (cx.tower.plan.line.action): Plan Line Action
            - jet_template (cx.tower.jet.template): Jet Template
            - jet (cx.tower.jet): Jet
            - _depth (int): Depth of the recursion
        """
        # 0. Get keyword arguments
        server = kwargs.get("server")
        jet_template = kwargs.get("jet_template")
        jet = kwargs.get("jet")
        _depth = kwargs.get("_depth", 0)

        # Control recursion depth
        _depth += 1
        if _depth > MAX_DEPTH:
            _logger.error("Max depth %d reached for variable %s", _depth, self.name)
            return

        TemplateMixin = self.env["cx.tower.template.mixin"]
        for key, var_value in variable_values.items():
            # Skip system variable values
            if not var_value or key == self.SYSTEM_VARIABLE_REFERENCE:
                continue

            # Render only if template is found
            if "{{" in var_value and "}}" in var_value:
                # Get variables used in value
                value_vars = TemplateMixin.get_variables_from_code(var_value)

                # Render variables used in value
                values_for_value = self._get_variable_values_by_references(
                    value_vars,
                    apply_modifiers=True,
                    server=server,
                    jet_template=jet_template,
                    jet=jet,
                    _depth=_depth,
                )

                # Render value using variables
                variable_values[key] = TemplateMixin.render_code_custom(
                    var_value, **values_for_value
                )

    def _apply_modifiers(self, variable_values):
        """Apply pre-defined Python expression to the dictionary
            of variable values.

        Args:
            variable_values (dict): variable values
            {variable_reference: value}
        """

        for variable_reference, value in variable_values.items():
            if not value:
                continue

            # ORM should cache resolved variables
            variable = self.get_by_reference(variable_reference)

            # Should never happen.. anyway
            if not variable:
                continue

            # Skip if no expression to apply
            if not variable.applied_expression:
                continue

            # Evaluate expression
            eval_context = variable._get_eval_context(value)
            try:
                safe_eval(
                    variable.applied_expression,
                    eval_context,
                    mode="exec",
                    nocopy=True,
                )
                variable_values[variable_reference] = eval_context.get("result", value)
            except Exception as e:
                _logger.error(
                    "Error evaluating applied expression for "
                    "variable %s value %s: %s",
                    variable.name,
                    value,
                    str(e),
                )

    @api.model
    def _get_system_variable_values(self, server=None, jet_template=None, jet=None):
        """
        Get the values for the `tower` system variable.
        This variable uses `tower.<var_provider>.<var_name>` format.
        E.g. `tower.server.ipv6`, `tower.tools.uuid`,
        `tower.jet_template.reference`, `tower.tools.now_underscore` etc.


        Args:
            server (cx.tower.server()): server record
            jet_template (cx.tower.jet.template()): jet template record
            jet (cx.tower.jet()): jet record

        Returns:
            dict(): `tower` values.
                {
                    'tools': {..helper tools vals...}
                    'server': {..server vals..},
                    'jet_template': {..jet template vals..},
                    'jet': {..jet vals..},
                }
        """
        return {
            "tools": self._parse_system_variable_tools(),
            "server": self._parse_system_variable_server(server),
            "jet_template": self._parse_system_variable_jet_template(jet_template),
            "jet": self._parse_system_variable_jet(jet),
        }

    def _parse_system_variable_server(self, server=None):
        """Parser system variable of `server` type.

        Args:
            server (cx.tower.server()): server record

        Returns:
            dict(): `server` values of the `tower` variable.
        """
        # Get current server
        values = {}
        if server:
            # Using sudo() to get all fields
            server = server.sudo()
            values = {
                "name": server.name,
                "reference": server.reference,
                "username": server.ssh_username,
                "partner_name": server.partner_id.name if server.partner_id else False,
                "ipv4": server.ip_v4_address,
                "ipv6": server.ip_v6_address,
                "status": server.status,
                "os": server.os_id.name if server.os_id else False,
                "url": server.url,
            }
            if server.url:
                url_parts = urlparse(server.url)
                values.update(
                    {
                        "hostname": url_parts.hostname,
                        "netloc": url_parts.netloc,
                        "port": url_parts.port,
                    }
                )
        return values

    def _parse_system_variable_jet_template(self, jet_template=None):
        """Parser system variable of `server` type.

        Args:
            jet_template (cx.tower.jet.template()): jet template record

        Returns:
            dict(): `jet_template` values of the `tower` variable.
        """
        # Get current server
        values = {}
        if jet_template:
            # Using sudo() to get all fields
            jet_template = jet_template.sudo()
            values = {
                "name": jet_template.name,
                "reference": jet_template.reference,
            }
        return values

    def _parse_system_variable_jet(self, jet=None):
        """Parser system variable of `jet` type.

        Args:
            jet (cx.tower.jet()): jet record
        """
        values = {}
        if jet:
            # Using sudo() to get all fields
            jet = jet.sudo()
            values = {
                "name": jet.name,
                "reference": jet.reference,
                "url": jet.url,
                "state": jet.state,
                "cloned_from": jet.jet_cloned_from_id.reference
                if jet.jet_cloned_from_id
                else False,
            }
            # Add URL parts if URL is set
            if jet.url:
                url_parts = urlparse(jet.url)
            else:
                url_parts = False
            values.update(
                {
                    "hostname": url_parts.hostname
                    if url_parts and url_parts.hostname
                    else False,
                    "netloc": url_parts.netloc
                    if url_parts and url_parts.netloc
                    else False,
                    "port": url_parts.port if url_parts and url_parts.port else False,
                }
            )
            # Add waypoint values if waypoint is set
            waypoint_data = {
                "reference": jet.waypoint_id.reference if jet.waypoint_id else False,
                "type": jet.waypoint_id.waypoint_template_id.reference
                if jet.waypoint_id
                else False,
            }
            # Add each metadata key-value pair to the waypoint data
            metadata = jet.waypoint_id.metadata if jet.waypoint_id else False
            if metadata:
                for key, value in metadata.items():
                    waypoint_data[key] = value
            values.update({"waypoint": waypoint_data})
        return values

    def _parse_system_variable_tools(self):
        """Parser system variable of `tools` type.

        Returns:
            dict(): `tools` values of the `tower` variable.
        """
        today = fields.Date.to_string(fields.Date.today())
        now = fields.Datetime.to_string(fields.Datetime.now())
        values = {
            "uuid": uuid.uuid4(),
            "today": today,
            "now": now,
            "today_underscore": re.sub(r"[-: .\/]", "_", today),
            "now_underscore": re.sub(r"[-: .\/]", "_", now),
        }
        return values
