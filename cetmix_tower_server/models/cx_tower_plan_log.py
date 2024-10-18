# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models

from .constants import PLAN_IS_EMPTY


class CxTowerPlanLog(models.Model):
    _name = "cx.tower.plan.log"
    _description = "Cetmix Tower Flight Plan Log"
    _order = "start_date desc, id desc"

    active = fields.Boolean(default=True)
    name = fields.Char(compute="_compute_name", compute_sudo=True, store=True)
    label = fields.Char(help="Custom label. Can be used for search/tracking")
    server_id = fields.Many2one(
        comodel_name="cx.tower.server", required=True, index=True, ondelete="restrict"
    )
    plan_id = fields.Many2one(
        string="Flight Plan",
        comodel_name="cx.tower.plan",
        required=True,
        index=True,
        ondelete="restrict",
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
    is_running = fields.Boolean(help="Plan is being executed right now")
    plan_line_executed_id = fields.Many2one(
        comodel_name="cx.tower.plan.line",
        help="Flight Plan line that is being currently executed",
    )
    command_log_ids = fields.One2many(
        comodel_name="cx.tower.command.log", inverse_name="plan_log_id", auto_join=True
    )
    plan_status = fields.Integer(string="Status")
    parent_flight_plan_log_id = fields.Many2one(
        "cx.tower.plan.log",
    )

    @api.depends("server_id.name", "name")
    def _compute_name(self):
        for rec in self:
            rec.name = ": ".join((rec.server_id.name, rec.plan_id.name))  # type: ignore

    @api.depends("finish_date")
    def _compute_duration(self):
        for plan_log in self:
            if plan_log.finish_date and plan_log.start_date:
                plan_log.duration = (
                    plan_log.finish_date - plan_log.start_date
                ).total_seconds()

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
            start_date (datetime) command start date time.
            **kwargs (dict): optional values
                Following keys are supported but not limited to:
                - "plan_log": {values passed to flightplan logger}
                - "log": {values passed to logger}
                - "key": {values passed to key parser}
                - "no_log" (bool): If True, no logs will be recorded for
                                   non-executable lines.
        Returns:
            cx.tower.plan.log(): New flightplan log record.
        """

        def get_executable_line(plan, server):
            """
            Generator to get each line and check if it's executable.
            """
            for line in plan.line_ids:
                yield line, line._is_executable_line(server)

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

        plan_log = self.sudo().create(vals)

        # Process each line until the first executable one is found
        for line, is_executable in get_executable_line(plan, server):
            if is_executable:
                line._execute(server, plan_log, **kwargs)
                break
            else:
                if self._context.get("no_log"):
                    continue
                line._skip(server, plan_log)
                break
        else:
            plan_log.sudo().write(
                {
                    "is_running": False,
                    "finish_date": fields.Datetime.now(),
                    "plan_status": PLAN_IS_EMPTY,
                }
            )

        return plan_log

    def finish(self, plan_status, **kwargs):
        """Finish plan execution

        Args:
            plan_status (Integer) plan execution code
            **kwargs (dict): optional values
        """
        values = {
            "is_running": False,
            "plan_status": plan_status,
            "finish_date": fields.Datetime.now(),
        }

        # Apply kwargs
        if kwargs:
            values.update(kwargs)
        self.sudo().write(values)
        self._plan_finished()

    def _plan_finished(self):
        """Triggered when flightplan in finished
        Inherit to implement your own hooks
        """
        for log in self:
            context_timestamp = fields.Datetime.context_timestamp(
                self, fields.Datetime.now()
            )
            if log.plan_status == 0:
                log.create_uid.notify_success(
                    message=_(
                        "%(timestamp)s<br/>"
                        "Flight Plan '%(name)s' finished successfully",
                        name=log.plan_id.name,
                        timestamp=context_timestamp,
                    ),
                    title=log.server_id.name,
                    sticky=True,
                )
            else:
                log.create_uid.notify_danger(
                    message=_(
                        "%(timestamp)s<br/>"
                        "Flight Plan '%(name)s'"
                        " finished with error. "
                        "Please check the flight plan log for details.",
                        name=log.plan_id.name,
                        timestamp=context_timestamp,
                    ),
                    title=log.server_id.name,
                    sticky=True,
                )
        return True

    def _plan_command_finished(self, command_log):
        """This function is triggered when a command from this log is finished.
        Next action is triggered based on command status (ak exit code)

        Args:
            command_log (cx.tower.command.log()): Command log object

        """
        self.ensure_one()
        # Get next line to execute
        self.plan_id._run_next_action(command_log)  # type: ignore
