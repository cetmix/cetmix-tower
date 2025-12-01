# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from operator import indexOf

from odoo import _, api, fields, models
from odoo.tools.safe_eval import expr_eval

from .constants import (
    ANOTHER_PLAN_RUNNING,
    PLAN_LINE_CONDITION_CHECK_FAILED,
    PLAN_LINE_NOT_ASSIGNED,
    PLAN_NOT_ASSIGNED,
    PLAN_NOT_COMPATIBLE_WITH_SERVER,
)


class CxTowerPlan(models.Model):
    """Cetmix Tower flight plan"""

    _name = "cx.tower.plan"
    _description = "Cetmix Tower Flight Plan"
    _inherit = [
        "cx.tower.reference.mixin",
        "cx.tower.access.mixin",
        "cx.tower.access.role.mixin",
        "cx.tower.tag.mixin",
    ]
    _order = "name asc"

    active = fields.Boolean(default=True)
    allow_parallel_run = fields.Boolean(
        help="If enabled, multiple instances of the same flight plan "
        "can be run on the same server at the same time.\n"
        "Otherwise, ANOTHER_PLAN_RUNNING status will be returned if another"
        " instance of the same flight plan is already running"
    )

    color = fields.Integer(help="For better visualization in views")
    server_ids = fields.Many2many(string="Servers", comodel_name="cx.tower.server")
    tag_ids = fields.Many2many(
        relation="cx_tower_plan_tag_rel",
        column1="plan_id",
        column2="tag_id",
    )
    line_ids = fields.One2many(
        string="Lines",
        comodel_name="cx.tower.plan.line",
        inverse_name="plan_id",
        auto_join=True,
        copy=True,
    )
    command_ids = fields.Many2many(
        string="Commands",
        comodel_name="cx.tower.command",
        relation="cx_tower_command_flight_plan_used_id_rel",
        column1="plan_id",
        column2="command_id",
        help="Commands used in this flight plan",
        compute="_compute_command_ids",
        store=True,
    )
    note = fields.Text()
    on_error_action = fields.Selection(
        string="On Error",
        selection=[
            ("e", "Exit with command exit code"),
            ("ec", "Exit with custom exit code"),
            ("n", "Run next command"),
        ],
        required=True,
        default="e",
        help="This action will be triggered on error "
        "if no command action can be applied",
    )
    custom_exit_code = fields.Integer(
        help="Will be used instead of the command exit code"
    )

    access_level_warn_msg = fields.Text(
        compute="_compute_command_access_level",
        compute_sudo=True,
    )

    # ---- Access. Add relation for mixin fields
    user_ids = fields.Many2many(
        relation="cx_tower_plan_user_rel",
    )
    manager_ids = fields.Many2many(
        relation="cx_tower_plan_manager_rel",
    )

    @api.depends("line_ids.command_id.access_level", "access_level")
    def _compute_command_access_level(self):
        """Check if the access level of a command in the plan
        is higher than the plan's access level"""
        for record in self:
            commands = record.mapped("line_ids").mapped("command_id")
            # Retrieve all commands associated with the flight plan
            commands_with_higher_access = commands.filtered(
                lambda c, access_level=record.access_level: c.access_level
                > access_level
            )
            if commands_with_higher_access:
                command_names = ", ".join(commands_with_higher_access.mapped("name"))
                record.access_level_warn_msg = _(
                    "The access level of command(s) '%(command_names)s' included in the"
                    " current Flight plan is higher than the access level of the"
                    " Flight plan itself. Please ensure that you want to allow"
                    " those commands to be run anyway.",
                    command_names=command_names,
                )
            else:
                record.access_level_warn_msg = False

    @api.depends("line_ids", "line_ids.command_id")
    def _compute_command_ids(self):
        """Compute command ids"""
        for plan in self:
            plan.command_ids = plan.line_ids.command_id

    def action_open_plan_logs(self):
        """
        Open current flight plan log records
        """
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_plan_log"
        )
        action["domain"] = [("plan_id", "=", self.id)]
        return action

    def _get_dependent_model_relation_fields(self):
        """Check cx.tower.reference.mixin for the function documentation"""
        res = super()._get_dependent_model_relation_fields()
        return res + ["line_ids"]

    def _is_plan_incompatible_with_server(self, server):
        """
        Check if the flight plan is compatible with the server.
        Note: this function uses the inverse logic to simplify the checks.

        Args:
            server (cx.tower.server()): Server object

        Returns:
            Char or False: Incompatible reason or False if compatible
        """

        # Check if the flight plan is compatible with the server
        if not self.server_ids:
            return False
        if server.id not in self.server_ids.ids:
            return _("Flight plan is not compatible with the server")

        # Check if the flight plan commands are compatible with the server
        for command in self.command_ids:
            # Check the entire command first
            if not command._check_server_compatibility(server):
                return _(
                    "Command %(command_name)s is not compatible with the server",
                    command_name=command.name,
                )  # pylint: disable=no-member

            # Check if the nested flight plan is compatible with the server
            if command.action == "plan":
                plan_check_result = (
                    command.flight_plan_id._is_plan_incompatible_with_server(server)
                )
                if plan_check_result:
                    return plan_check_result

        return False

    def _get_post_create_fields(self):
        res = super()._get_post_create_fields()
        return res + ["line_ids"]

    def _run_single(self, server, **kwargs):
        """Run single Flight Plan on a single server

        Args:
            server (cx.tower.server()): Server object
            kwargs (dict): Optional arguments
                Following are supported but not limited to:
                    - "plan_log": {values passed to flightplan logger}
                    - "log": {values passed to logger}
                    - "key": {values passed to key parser}
                    - "variable_values", dict(): custom variable values
                        in the format of `{variable_reference: variable_value}`
                        eg `{'odoo_version': '16.0'}`
                        Will be applied only if user has write access to the server.

        Returns:
            log_record (cx.tower.plan.log()): plan log record
        """

        self.ensure_one()
        # Ensure we have a single server record
        server.ensure_one()

        # Check plan access before running
        # This is needed to avoid possible access violations
        self.check_access("read")

        # Access log as root to bypass access restrictions
        plan_log_obj = self.env["cx.tower.plan.log"].sudo()

        # Check if flight plan and all its commands can be run on this server
        # This check is skipped if 'from_command' context key is set to True
        if not self.env.context.get("from_command"):
            plan_is_incompatible = self._is_plan_incompatible_with_server(server)
            if plan_is_incompatible:
                # Create a log record with the custom message and exit
                plan_log_kwargs = kwargs.get("plan_log", {})
                plan_log_kwargs["custom_message"] = plan_is_incompatible
                kwargs["plan_log"] = plan_log_kwargs
                plan_log = plan_log_obj.record(
                    server=server,
                    plan=self,
                    status=PLAN_NOT_COMPATIBLE_WITH_SERVER,
                    **kwargs,
                )
                return plan_log

        # Check if the same plan is being run on this server right now
        if not self.allow_parallel_run or self.env.context.get(
            "prevent_plan_recursion"
        ):
            running_count = plan_log_obj.search_count(
                [
                    ("server_id", "=", server.id),
                    ("plan_id", "=", self.id),  # pylint: disable=no-member
                    ("is_running", "=", True),
                ]
            )
            if running_count > 0:
                plan_log = plan_log_obj.record(
                    server=server, plan=self, status=ANOTHER_PLAN_RUNNING, **kwargs
                )
                return plan_log

        # Start Flight Plan and return the log record
        return plan_log_obj.start(server, self, fields.Datetime.now(), **kwargs)

    def _get_next_action_values(self, command_log):
        """Get next action values based of previous command result:

            - Action to proceed
            - Exit code
            - Next line of the plan if next line should be run

        Args:
            command_log (cx.tower.command.log()): Command log record

        Returns:
            action, exit_code, next_line (Selection, Integer, cx.tower.plan.line())

        """
        # Iterate all actions and return the first matching one.
        # If no action is found return the default plan values
        # If the line is the last one return last command exit code

        if not command_log.plan_log_id:  # Exit with custom code "Plan not found"
            return "ec", PLAN_NOT_ASSIGNED, None

        current_line = command_log.plan_log_id.plan_line_executed_id
        if not current_line:
            return "ec", PLAN_LINE_NOT_ASSIGNED, None

        # Default values
        exit_code = command_log.command_status
        server = command_log.server_id

        # Check line condition
        variable_values = (
            command_log.variable_values or command_log.plan_log_id.variable_values or {}
        )
        if not current_line._is_executable_line(
            server, variable_values=variable_values
        ):
            # Immediately return to the next line if condition fails
            return self._get_next_action_state(
                "n", PLAN_LINE_CONDITION_CHECK_FAILED, current_line
            )

        # Check plan action lines
        for action_line in current_line.action_ids:
            conditional_expression = (
                f"{exit_code} {action_line.condition} {action_line.value_char}"
            )
            # Evaluate expression using safe_eval
            if expr_eval(conditional_expression):
                action = action_line.action
                # Use custom exit code if action requires it
                if action == "ec" and action_line.custom_exit_code:
                    exit_code = action_line.custom_exit_code

                # Apply action-defined values into the variable values context
                for variable_value in action_line.variable_value_ids:
                    ref = variable_value.variable_id.reference
                    variable_values[ref] = variable_value.value_char

                # Persist the updated custom values only in logs
                # so they remain available within the current flight plan context
                updated_values = dict(variable_values)
                command_log.variable_values = updated_values
                if command_log.plan_log_id:
                    command_log.plan_log_id.variable_values = updated_values

                return self._get_next_action_state(action, exit_code, current_line)

        # If no action matched, fallback to default ones
        return self._get_next_action_state(None, exit_code, current_line)

    def _get_next_action_state(self, action, exit_code, current_line):
        """
        Determine the next action, exit code, and next line based on the current state.
        """
        lines = current_line.plan_id.line_ids
        is_last_line = current_line == lines[-1]

        # If no conditions were met fallback to default ones
        if not action:
            action = "n" if exit_code == 0 else current_line.plan_id.on_error_action

            # Exit with custom code
            if action == "ec":
                exit_code = current_line.plan_id.custom_exit_code

        # Determine the next line if current is not the last one
        next_line = None
        if action == "n" and not is_last_line:
            next_line = lines[indexOf(lines, current_line) + 1]

        if is_last_line:
            action = "e"

        return action, exit_code, next_line

    def _run_next_action(self, command_log):
        """Run next action based on the command result

        Args:
            command_log (cx.tower.command.log()): Command log record
        """
        self.ensure_one()
        action, exit_code, plan_line = self._get_next_action_values(command_log)
        plan_log = command_log.plan_log_id

        # Update log message
        if exit_code == PLAN_LINE_CONDITION_CHECK_FAILED:
            # save log exit code as success
            exit_code = 0

        # Run next line
        if action == "n" and plan_line:
            server = command_log.server_id
            variable_values = command_log.variable_values or plan_log.variable_values
            if plan_line._is_executable_line(server, variable_values=variable_values):
                plan_line._run(server, plan_log, variable_values=variable_values)
            else:
                plan_line._skip(
                    server,
                    plan_log,
                    log={"variable_values": dict(variable_values or {})},
                )

        # Exit
        if action in ["e", "ec"]:
            plan_log.finish(exit_code)

        # NB: we are not putting any fallback here in case
        # someone needs to inherit and extend this function
