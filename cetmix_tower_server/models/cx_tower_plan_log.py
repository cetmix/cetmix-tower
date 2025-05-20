# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import logging

from odoo import _, api, fields, models

from .constants import PLAN_IS_EMPTY, PLAN_STOPPED

_logger = logging.getLogger(__name__)


class CxTowerPlanLog(models.Model):
    """Flight Plan Log"""

    _name = "cx.tower.plan.log"
    _description = "Cetmix Tower Flight Plan Log"
    _order = "start_date desc, id desc"

    active = fields.Boolean(default=True)
    name = fields.Char(compute="_compute_name", compute_sudo=True, store=True)
    label = fields.Char(
        help="Custom label. Can be used for search/tracking",
        index="trigram",
    )
    server_id = fields.Many2one(
        comodel_name="cx.tower.server", required=True, index=True, ondelete="cascade"
    )
    jet_template_id = fields.Many2one(
        comodel_name="cx.tower.jet.template",
        readonly=True,
        index=True,
        ondelete="cascade",
    )
    jet_template_install_id = fields.Many2one(
        string="Jet Template Install Job",
        comodel_name="cx.tower.jet.template.install",
        readonly=True,
        ondelete="cascade",
        index=True,
        help="Jet Template Install/Uninstall record being run. ",
    )
    jet_id = fields.Many2one(
        comodel_name="cx.tower.jet",
        readonly=True,
        index=True,
        ondelete="cascade",
    )
    jet_action_id = fields.Many2one(
        comodel_name="cx.tower.jet.action",
        readonly=True,
        help="Used to track flight plans executed by jet actions",
    )
    waypoint_id = fields.Many2one(
        comodel_name="cx.tower.jet.waypoint",
        help="Waypoint this plan log belongs to",
    )

    plan_id = fields.Many2one(
        string="Flight Plan",
        comodel_name="cx.tower.plan",
        required=True,
        index=True,
        ondelete="cascade",
    )
    access_level = fields.Selection(
        related="plan_id.access_level",
        readonly=True,
        store=True,
        index=True,
    )

    # -- Time
    start_date = fields.Datetime(string="Started")
    finish_date = fields.Datetime(string="Finished")
    duration = fields.Float(
        help="Time consumed for execution, seconds",
        compute="_compute_duration",
        store=True,
    )
    duration_current = fields.Float(
        string="Duration, sec",
        compute="_compute_duration_current",
        help="For how long a flight plan is already running",
    )

    # -- Commands
    is_running = fields.Boolean(
        help="Plan is being executed right now", compute="_compute_duration", store=True
    )
    is_stopped = fields.Boolean(
        string="Stopped", default=False, help="Flight plan was stopped by user"
    )
    plan_line_executed_id = fields.Many2one(
        comodel_name="cx.tower.plan.line",
        help="Flight Plan line that is being currently executed",
    )
    command_log_ids = fields.One2many(
        comodel_name="cx.tower.command.log", inverse_name="plan_log_id", auto_join=True
    )
    plan_status = fields.Integer(
        string="Status",
        help="0 if plan is finished successfully. \n"
        "-301 if another instance of this flight plan is running, \n"
        "-302 if plan is empty, \n"
        "-303 if plan reference is missing, \n"
        "-304 if plan line reference is missing, \n"
        "-306 if plan is not compatible with server,\n"
        "-308 if plan is stopped by user",
    )
    custom_message = fields.Text(
        help="Custom message to be displayed in the plan log",
    )
    parent_flight_plan_log_id = fields.Many2one(
        "cx.tower.plan.log", string="Main Log", ondelete="cascade"
    )
    scheduled_task_id = fields.Many2one(
        "cx.tower.scheduled.task",
        ondelete="set null",
        help="Scheduled task that triggered this flight plan",
    )
    variable_values = fields.Json(
        default={},
        help="Custom variable values passed to the flight plan",
    )

    @api.depends("server_id.name", "plan_id.name")
    def _compute_name(self):
        for rec in self:
            rec.name = ": ".join((rec.server_id.name, rec.plan_id.name))  # type: ignore

    @api.depends("start_date", "finish_date")
    def _compute_duration(self):
        for plan_log in self:
            # Not started yet
            if not plan_log.start_date:
                continue

            # If plan is finished, compute duration
            if plan_log.finish_date:
                plan_log.update(
                    {
                        "duration": (
                            plan_log.finish_date - plan_log.start_date
                        ).total_seconds(),
                        "is_running": False,
                    }
                )
                continue

            # If plan is running, set is_running to True
            plan_log.is_running = True

    @api.depends("is_running")
    def _compute_duration_current(self):
        """Shows relative time between now() and start time for running plans,
        and computed duration for finished ones.
        """
        now = fields.Datetime.now()
        for plan_log in self:
            if plan_log.is_running:
                plan_log.duration_current = (now - plan_log.start_date).total_seconds()
            else:
                plan_log.duration_current = plan_log.duration

    def start(self, server, plan, start_date=None, **kwargs):
        """
        Runs plan on server.
        Creates initial log records for each command that cannot be executed until
        it finds the first executable command.

        Args:
            server (cx.tower.server()) server.
            plan (cx.tower.plan()) Flight Plan.
            start_date (datetime) flight plan start date time.
            **kwargs (dict): optional values
                Following keys are supported but not limited to:
                - "plan_log": {values passed to flightplan logger}
                - "log": {values passed to logger}
                - "key": {values passed to key parser}
                - "no_command_log" (bool): If True, no logs will be recorded for
                                   non-executable lines.
                - "variable_values", dict(): custom variable values
                    in the format of `{variable_reference: variable_value}`
                    eg `{'odoo_version': '16.0'}`
                    Will be applied only if user has write access to the server.
        Returns:
            cx.tower.plan.log(): New flightplan log record.
        """

        def get_executable_line(
            plan, server, jet_template=None, jet=None, variable_values=None
        ):
            """
            Generator to get each line and check if it's executable.
            Args:
                plan (cx.tower.plan()): Flight Plan.
                server (cx.tower.server()): Server.
                jet_template (cx.tower.jet.template()): Jet Template.
                jet (cx.tower.jet()): Jet.
            Returns:
                tuple: (line, is_executable)
            """
            for line in plan.line_ids:
                yield (
                    line,
                    line._is_executable_line(
                        server=server,
                        jet_template=jet_template,
                        jet=jet,
                        variable_values=variable_values,
                    ),
                )

        vals = {
            "server_id": server.id,
            "plan_id": plan.id,
            "is_running": True,
            "start_date": start_date or fields.Datetime.now(),
        }

        # Extract and apply plan log kwargs
        plan_log_kwargs = kwargs.get("plan_log")
        if plan_log_kwargs:
            vals.update(plan_log_kwargs)

        # Extract and apply variable values
        variable_values = kwargs.get("variable_values")
        if variable_values:
            vals["variable_values"] = variable_values

        plan_log = self.sudo().create(vals)

        # Process each line until the first executable one is found
        for line, is_executable in get_executable_line(
            plan=plan,
            server=server,
            jet_template=plan_log.jet_template_id,
            jet=plan_log.jet_id,
            variable_values=variable_values,
        ):
            if is_executable:
                line._run(server=server, plan_log_record=plan_log, **kwargs)
                break
            else:
                if self._context.get("no_command_log"):
                    continue
                line._skip(
                    server,
                    plan_log,
                    log={
                        "variable_values": dict(variable_values or {}),
                        "jet_template_id": plan_log.jet_template_id.id
                        if plan_log.jet_template_id
                        else None,
                        "jet_id": plan_log.jet_id.id if plan_log.jet_id else None,
                    },
                )
                break
        else:
            plan_log.finish(plan_status=PLAN_IS_EMPTY)

        return plan_log

    def stop(self):
        """
        Force stop this plan log (and currently running command if possible).
        """
        user_name = self.env.user.name
        for log in self:
            if not log.is_running:
                continue

            # Finish plan log
            log.finish(
                plan_status=PLAN_STOPPED,
                custom_message=_("Stopped by user %(user)s", user=user_name),
                is_stopped=True,
            )

            # Stop running command
            running_cmd_logs = log.command_log_ids.filtered(lambda c: c.is_running)
            running_cmd_logs.stop()

    def action_stop(self):
        """
        Action to stop the running plans.
        """
        self.stop()

        if len(self) > 1:  # more than one plan is running
            title = _("Flight Plans Stopped")
            message = ", ".join([plan.name for plan in self])
        else:
            title = _("Flight Plan Stopped")
            message = self.name

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "sticky": False,
                "next": {
                    "type": "ir.actions.act_window_close",
                },
            },
        }

    def finish(self, plan_status, **kwargs):
        """Finish plan execution

        Args:
            plan_status (Integer) plan execution code
            **kwargs (dict): optional values
        """
        self.ensure_one()

        values = {
            "is_running": False,
            "plan_status": plan_status,
            "finish_date": fields.Datetime.now(),
        }

        # Apply kwargs
        if kwargs:
            values.update(kwargs)
        self.sudo().write(values)

        # Call the plan finished hook
        # Use try/except to ensure that the plan finished hook is called
        try:
            # Savepoint to ensure that values are stored
            # if something goes wrong.
            with self.env.cr.savepoint():
                self._plan_finished()
        except Exception as e:
            _logger.warning(
                "Post-finish hook for plan '%s' failed: %s", self.plan_id.name, e
            )
        # Continue with the rest of the logic

        # Jet Template action: only if it's not a sub-plan
        # NB: Jet Template is always set automatically even if
        # it's not provided explicitly when the plan is run.
        if not self.jet_template_id or self.parent_flight_plan_log_id:
            return

        # Waypoint action: only if it's not a sub-plan
        if self.waypoint_id:
            try:
                with self.env.cr.savepoint():
                    self.waypoint_id._plan_finished(self)
            except Exception as e:
                _logger.warning(
                    "Post-finish hook for waypoint '%s' failed: %s",
                    self.waypoint_id.name,
                    e,
                )

        # Finish template install/uninstall
        if self.jet_template_install_id:
            try:
                with self.env.cr.savepoint():
                    self.jet_template_install_id._flight_plan_finished(
                        plan_status=self.plan_status,
                    )
            except Exception as e:
                _logger.warning(
                    "Post-finish hook for template install/uninstall "
                    "'%s'"
                    " failed: %s",
                    self.jet_template_install_id.name,
                    e,
                )

        # Jet
        if self.jet_id and self.jet_action_id:
            try:
                with self.env.cr.savepoint():
                    self.jet_id._flight_plan_finished(
                        plan_status=self.plan_status,
                    )
            except Exception as e:
                _logger.warning(
                    "Post-finish hook for jet '%s' failed: %s", self.jet_id.name, e
                )

    def record(self, server, plan, status, **kwargs):
        """
        Record plan log without running it.

        Args:
            server (cx.tower.server()) server.
            plan (cx.tower.plan()) Flight Plan.
            status (int) plan execution code
            start_date (datetime) flight plan start date time.
            finish_date (datetime) flight plan finish date time.
            **kwargs (dict): optional values
                Following keys are supported but not limited to:
                - "plan_log": {values passed to flightplan logger}
                - "log": {values passed to logger}
                - "key": {values passed to key parser}
                - "no_command_log" (bool): If True, no logs will be recorded for
                                   non-executable lines.
        Returns:
            cx.tower.plan.log(): New flightplan log record.
        """

        vals = {
            "server_id": server.id,
            "plan_id": plan.id,
            "start_date": fields.Datetime.now(),
        }

        # Extract and apply plan log kwargs
        plan_log_kwargs = kwargs.get("plan_log")
        if plan_log_kwargs:
            vals.update(plan_log_kwargs)

        plan_log = self.sudo().create(vals)
        plan_log.finish(plan_status=status)
        return plan_log

    def _plan_finished(self):
        """Triggered when flightplan in finished
        Inherit to implement your own hooks

        Returns:
            bool: True if event was handled
        """
        self.ensure_one()

        # Do not notify if a plan that was run from another plan has been executed
        if self.parent_flight_plan_log_id:
            return True

        # Check if notifications are enabled
        ICP_sudo = self.env["ir.config_parameter"].sudo()
        notification_type_success = ICP_sudo.get_param(
            "cetmix_tower_server.notification_type_success"
        )
        notification_type_error = ICP_sudo.get_param(
            "cetmix_tower_server.notification_type_error"
        )

        # Prepare notifications
        if not notification_type_success and not notification_type_error:
            return True

        # Use context timestamp to avoid timezone issues
        context_timestamp = fields.Datetime.context_timestamp(
            self, fields.Datetime.now()
        )

        # Action for button
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_plan_log"
        )

        context = self.env.context.copy()
        params = dict(context.get("params") or {})
        params["button_name"] = _("View Log")
        context["params"] = params

        # Add record id and context to the action
        action.update(
            {
                "context": context,
                "res_id": self.id,
                "views": [(False, "form")],
            }
        )

        # Send notification only if not a jet-related plan
        if (
            self.plan_status == 0
            and notification_type_success
            and not self.jet_template_id
        ):
            # Success notification
            self.create_uid.notify_success(
                message=_(
                    "%(timestamp)s<br/>" "Flight Plan '%(name)s' finished successfully",
                    name=self.plan_id.name,
                    timestamp=context_timestamp,
                ),
                title=self.server_id.name,
                sticky=notification_type_success == "sticky",
                action=action,
            )

        # Error notification
        # They are shown for jet-related plans and template installation/uninstallation
        # as well to simplify the debugging process.
        if self.plan_status != 0 and notification_type_error:
            self.create_uid.notify_danger(
                message=_(
                    "%(timestamp)s<br/>"
                    "Flight Plan '%(name)s'"
                    " finished with error",
                    name=self.plan_id.name,
                    timestamp=context_timestamp,
                ),
                title=self.server_id.name,
                sticky=notification_type_error == "sticky",
                action=action,
            )

        return True

    def _plan_command_finished(self, command_log):
        """This function is triggered when a command from this log is finished.
        Next action is triggered based on command status (ak exit code)

        Args:
            command_log (cx.tower.command.log()): Command log object

        """
        self.ensure_one()

        # Prevent scheduling further actions if this log was stopped
        if self.is_stopped:
            return

        # Update plan log variable values from command log
        # Overwrite with command log values (last command's values take precedence)
        self.variable_values = command_log.variable_values

        # Get next line to execute
        self.plan_id._run_next_action(command_log)  # type: ignore
