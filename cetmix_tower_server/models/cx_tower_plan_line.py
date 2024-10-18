# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.safe_eval import safe_eval

from .constants import PLAN_LINE_CONDITION_CHECK_FAILED


class CxTowerPlanLine(models.Model):
    _name = "cx.tower.plan.line"
    _order = "sequence, plan_id"
    _description = "Cetmix Tower Flight Plan Line"

    active = fields.Boolean(related="plan_id.active", readonly=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(related="command_id.name", readonly=True)
    plan_id = fields.Many2one(
        string="Flight Plan", comodel_name="cx.tower.plan", auto_join=True
    )
    command_id = fields.Many2one(comodel_name="cx.tower.command", required=True)
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
        help="Actions trigger based on command result."
        " If empty next command will be executed",
    )
    command_code = fields.Text(related="command_id.code", readonly=True)

    access_level = fields.Selection(
        related="plan_id.access_level",
        readonly=True,
        store=True,
    )
    condition = fields.Char(
        string="Condition",
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

    @api.constrains("command_id")
    def _check_command_id(self):
        """
        Check recursive plan line execution. If the command refers to another plan,
        make sure there are no recursive references.
        """
        for line in self:
            visited_plans = set()
            self._check_recursive_plan(line.command_id, visited_plans)

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

    def _execute(self, server, plan_log_record, **kwargs):
        """Execute command from the Flight Plan line

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

        # Pass plan_log to command so it will be saved in command log
        log_vals = kwargs.get("log", {})
        log_vals.update({"plan_log_id": plan_log_record.id})
        kwargs.update({"log": log_vals})

        # Set 'sudo' value
        use_sudo = self.use_sudo and server.use_sudo
        # Use sudo to bypass access rules for execute command with higher access level
        command_id = self.sudo().command_id

        # Set path
        path = self.path or self.command_id.path
        server.execute_command(command_id, path, sudo=use_sudo, **kwargs)

    def _is_executable_line(self, server):
        """
        Check if this line can be executed based on its condition.

        Args:
            server (cx.tower.server()): The server on which conditions are checked.

        Returns:
            bool: True if the line can be executed, otherwise False.
        """
        self.ensure_one()
        condition = self.condition
        if condition:
            variables = self.command_id.get_variables_from_code(condition)
            if variables:
                variable_values_dict = (
                    server.get_variable_values(variables) if variables else {}
                )
                variable_values = variable_values_dict.get(server.id, {})
                condition = self.command_id.render_code_custom(
                    condition, pythonic_mode=True, **variable_values
                )

            # For evaluate a string that contains an expression that mostly uses
            # Python constants, arithmetic expressions and the objects directly provided
            # in context we need use `safe_eval`
            return safe_eval(condition)

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
