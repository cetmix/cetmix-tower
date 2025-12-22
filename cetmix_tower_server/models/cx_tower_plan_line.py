# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval

from .constants import PLAN_LINE_CONDITION_CHECK_FAILED

_logger = logging.getLogger(__name__)


class CxTowerPlanLine(models.Model):
    """Flight Plan Line"""

    _name = "cx.tower.plan.line"
    _inherit = [
        "cx.tower.reference.mixin",
    ]
    _order = "sequence, plan_id"
    _description = "Cetmix Tower Flight Plan Line"

    active = fields.Boolean(related="plan_id.active", readonly=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(related="command_id.name", readonly=True)
    plan_id = fields.Many2one(
        string="Flight Plan",
        comodel_name="cx.tower.plan",
        auto_join=True,
        ondelete="cascade",
    )
    action = fields.Selection(
        selection=lambda self: self.command_id._selection_action(),
        compute="_compute_action",
        required=True,
        readonly=False,
    )
    command_id = fields.Many2one(
        comodel_name="cx.tower.command",
        required=True,
        ondelete="restrict",
        domain="[('action', '=', action)]",
    )
    note = fields.Text(related="command_id.note", readonly=True)
    path = fields.Char(
        help="Location where command will be executed. Overrides command default path. "
        "You can use {{ variables }} in path",
    )

    use_sudo = fields.Boolean(
        help="Will use sudo based on server settings."
        "If no sudo is configured will run without sudo"
    )
    action_ids = fields.One2many(
        string="Actions",
        comodel_name="cx.tower.plan.line.action",
        inverse_name="line_id",
        auto_join=True,
        copy=True,
        help="Actions trigger based on command result."
        " If empty next command will be executed",
    )
    command_code = fields.Text(
        related="command_id.code",
        readonly=True,
    )
    tag_ids = fields.Many2many(related="command_id.tag_ids", readonly=True)
    access_level = fields.Selection(
        related="plan_id.access_level",
        readonly=True,
        store=True,
    )
    condition = fields.Char(
        help="Conditions under which this Flight Plan Line "
        "will be launched. e.g.: {{ odoo_version}} == '14.0'",
    )
    variable_ids = fields.Many2many(
        comodel_name="cx.tower.variable",
        relation="cx_tower_plan_line_variable_rel",
        column1="plan_line_id",
        column2="variable_id",
        string="Variables",
        compute="_compute_variable_ids",
        store=True,
    )
    # -- Command related entities
    plan_run_id = fields.Many2one(
        comodel_name="cx.tower.plan",
        related="command_id.flight_plan_id",
        readonly=True,
        string="Run Flight Plan",
    )
    plan_run_line_ids = fields.One2many(
        comodel_name="cx.tower.plan.line",
        related="command_id.flight_plan_id.line_ids",
        string="Flight Plan Lines",
        readonly=True,
    )
    file_template_id = fields.Many2one(
        comodel_name="cx.tower.file.template",
        related="command_id.file_template_id",
        readonly=True,
    )
    file_template_code = fields.Text(
        string="Template Code",
        related="file_template_id.code",
        readonly=True,
    )

    @api.depends("condition")
    def _compute_variable_ids(self):
        """
        Compute variable_ids based on condition field.
        """
        template_mixin_obj = self.env["cx.tower.template.mixin"]
        for record in self:
            record.variable_ids = template_mixin_obj._prepare_variable_commands(
                ["condition"], force_record=record
            )

    def _compute_action(self):
        """
        Compute action based on command.
        """

        # We set action only once, so there is no 'depends' in this function
        for record in self:
            if record.action:
                continue
            if record.command_id:
                record.action = record.command_id.action
            else:
                record.action = False

    @api.constrains("command_id")
    def _check_command_id(self):
        """
        Check recursive plan line execution.
        """
        for line in self:
            # Check recursive plan line execution
            visited_plans = set()
            self._check_recursive_plan(line.command_id, visited_plans)

    @api.onchange("action")
    def _inverse_action(self):
        """
        Reset command when action changes.
        """
        self.command_id = False

    def _check_recursive_plan(self, command, visited_plans):
        """
        Recursively check if the command plan creates a cycle.
        Raise a ValidationError if a cycle is detected.
        """
        if command.flight_plan_id and command.action == "plan":
            if command.flight_plan_id.id in visited_plans:
                raise ValidationError(
                    _(
                        "Recursive plan call detected in plan %(name)s.",
                        name=command.flight_plan_id.name,
                    )
                )
            visited_plans.add(command.flight_plan_id.id)
            # recursively check the lines in the plan
            for line in command.flight_plan_id.line_ids:
                self._check_recursive_plan(line.command_id, visited_plans)

    def _run(self, server, plan_log_record, **kwargs):
        """Run command from the Flight Plan line

        Args:
            server (cx.tower.server()): Server object
            plan_log_record (cx.tower.plan.log()): Log record object
            kwargs (dict): Optional arguments
                Following are supported but not limited to:
                    - "plan_log": {values passed to flightplan logger}
                    - "log": {values passed to command logger}
                    - "key": {values passed to key parser}

        """
        self.ensure_one()

        # Set current line as currently executed in log
        plan_log_record.plan_line_executed_id = self

        # It is necessary to save information about which plan log
        # was created for a command log that has the command action “plan”
        flight_plan_command_log = kwargs.get("flight_plan_command_log")
        if flight_plan_command_log:
            flight_plan_command_log.triggered_plan_log_id = plan_log_record.id

        # Pass plan_log to command so it will be saved in command log
        log_vals = kwargs.get("log", {})
        log_vals.update({"plan_log_id": plan_log_record.id})
        kwargs.update({"log": log_vals})

        # Set 'sudo' value
        use_sudo = self.use_sudo and server.use_sudo

        # Use sudo to bypass access rules for execute command with higher access level
        command_as_root = self.sudo().command_id

        # Set path
        path = self.path or command_as_root.path
        server.run_command(command_as_root, path, sudo=use_sudo, **kwargs)

    def _is_executable_line(self, server, variable_values=None):
        """
        Check if this line can be executed based on its condition.

        Args:
            server (cx.tower.server()): The server on which conditions are checked.
            variable_values (dict, optional): Custom values provided when running the
                flight plan. These values are merged with server variables when
                rendering the condition.

        Returns:
            bool: True if the line can be executed, otherwise False.
        """
        self.ensure_one()
        condition = self.condition
        if condition:
            # Collect variable references used in the condition
            variables = self.command_id.get_variables_from_code(condition)

            # Values from server variables referenced in the condition
            server_values = {}
            if variables:
                variable_values_dict = server.get_variable_values(variables)
                server_values = variable_values_dict.get(server.id, {}) or {}

            # Merge with custom values passed to the flight plan (if any)
            merged_values = {**server_values, **(variable_values or {})}

            # Render condition with all available values (in pythonic mode)
            if merged_values:
                condition = self.command_id.render_code_custom(
                    condition, pythonic_mode=True, **merged_values
                )

            # For evaluate a string that contains an expression that mostly uses
            # Python constants, arithmetic expressions and the objects directly provided
            # in context we need use `safe_eval`
            # We catch all exceptions and return False to avoid raising an exception
            try:
                result = safe_eval(condition)
            except Exception as e:
                _logger.error(
                    "Error evaluating condition '%s' for plan line '%s' "
                    "in plan '%s' for server '%s'. Line is skipped. Error: %s",
                    condition,
                    self.name,
                    self.plan_id.name,
                    server.name,
                    str(e),
                )
                result = False
            return result

        return True  # Assume the line can be executed if no condition is specified

    def _skip(self, server, plan_log_record, **kwargs):
        """
        Triggered when plan line skipped by condition
        """
        self.ensure_one()

        # Set current line as currently executed in log
        plan_log_record.plan_line_executed_id = self

        # Log the unsuccessful execution attempt
        now = fields.Datetime.now()
        log_vals = kwargs.get("log", {})

        self.env["cx.tower.command.log"].record(
            server.id,
            self.command_id.id,
            now,
            now,
            PLAN_LINE_CONDITION_CHECK_FAILED,
            None,
            _("Plan line condition check failed."),
            plan_log_id=plan_log_record.id,
            condition=self.condition,
            is_skipped=True,
            **log_vals,
        )

    def _get_dependent_model_relation_fields(self):
        """Check cx.tower.reference.mixin for the function documentation"""
        res = super()._get_dependent_model_relation_fields()
        return res + ["action_ids"]

    def _get_pre_populated_model_data(self):
        """Check cx.tower.reference.mixin for the function documentation"""
        res = super()._get_pre_populated_model_data()
        res.update({"cx.tower.plan.line": ["cx.tower.plan", "plan_id"]})
        return res
