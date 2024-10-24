# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models


class CxTowerCommandLog(models.Model):
    _name = "cx.tower.command.log"
    _description = "Cetmix Tower Command Log"
    _order = "start_date desc, id desc"

    active = fields.Boolean(default=True)
    name = fields.Char(compute="_compute_name", compute_sudo=True, store=True)
    label = fields.Char(help="Custom label. Can be used for search/tracking")
    server_id = fields.Many2one(
        comodel_name="cx.tower.server", required=True, index=True, ondelete="restrict"
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
    # -- Command
    is_running = fields.Boolean(help="Command is being executed right now")
    command_id = fields.Many2one(
        comodel_name="cx.tower.command", required=True, index=True, ondelete="restrict"
    )
    command_action = fields.Selection(related="command_id.action")
    path = fields.Char(string="Execution Path", help="Where command was executed")
    code = fields.Text(string="Command Code")
    command_status = fields.Integer(string="Exit Code")
    command_response = fields.Text(string="Response")
    command_error = fields.Text(string="Error")
    use_sudo = fields.Selection(
        string="Use sudo",
        selection=[("n", "Without password"), ("p", "With password")],
        help="Run commands using 'sudo'",
    )
    condition = fields.Char(
        readonly=True,
    )
    is_skipped = fields.Boolean(
        readonly=True,
    )

    # -- Flight Plan
    plan_log_id = fields.Many2one(comodel_name="cx.tower.plan.log", ondelete="cascade")
    triggered_plan_log_id = fields.Many2one(comodel_name="cx.tower.plan.log")

    @api.depends("name", "command_id.name")
    def _compute_name(self):
        for rec in self:
            rec.name = ": ".join((rec.server_id.name, rec.command_id.name))  # type: ignore

    @api.depends("finish_date")
    def _compute_duration(self):
        for command_log in self:
            if command_log.finish_date and command_log.start_date:
                command_log.duration = (
                    command_log.finish_date - command_log.start_date
                ).total_seconds()

    def _compute_duration_current(self):
        """Shows relative time between now() and start time for running commands,
        and computed duration for finished ones.
        """
        now = fields.Datetime.now()
        for command_log in self:
            if command_log.is_running:
                command_log.duration_current = (
                    now - command_log.start_date
                ).total_seconds()
            else:
                command_log.duration_current = command_log.duration

    def start(self, server_id, command_id, start_date=None, **kwargs):
        """Creates initial log record when command is started

        Args:
            server_id (int) id of the server.
            command_id (int) id of the command.
            start_date (datetime) command start date time.
            **kwargs (dict): optional values
        Returns:
            (cx.tower.command.log()) new command log record or False
        """
        vals = {
            "server_id": server_id,
            "command_id": command_id,
            "is_running": True,
            "start_date": start_date if start_date else fields.Datetime.now(),
        }
        # Apply kwargs
        vals.update(kwargs)
        log_record = self.sudo().create(vals)
        return log_record

    def finish(
        self, finish_date=None, status=None, response=None, error=None, **kwargs
    ):
        """Save final command result when command is finished

        Args:
            log_record (cx.tower.command.log()): Log record
            finish_date (Datetime): command finish date time.
            **kwargs (dict): optional values
        """
        now = fields.Datetime.now()

        for rec in self.sudo():
            # Duration
            date_finish = finish_date if finish_date else now

            vals = {
                "is_running": False,
                "finish_date": date_finish,
                "command_status": -1 if status is None else status,
                "command_response": response,
                "command_error": error,
            }
            # Apply kwargs and write
            vals.update(kwargs)
            rec.write(vals)

            # Trigger post finish hook
            rec._command_finished()

    def record(
        self,
        server_id,
        command_id,
        start_date,
        finish_date,
        status=0,
        response=None,
        error=None,
        **kwargs,
    ):
        """Record completed command directly without using start/stop

        Args:
            server_id (int) id of the server.
            command_id (int) id of the command.
            start_date (datetime) command start date time.
            finish_date (datetime) command finish date time.
            status (int, optional): command execution status. Defaults to 0.
            response (list, optional): SSH response. Defaults to None.
            error (list, optional): SSH error. Defaults to None.
            **kwargs (dict): values to store
        Returns:
            (cx.tower.command.log()) new command log record
        """
        vals = kwargs or {}
        vals.update(
            {
                "server_id": server_id,
                "command_id": command_id,
                "start_date": start_date,
                "finish_date": finish_date,
                "command_status": status,
                "command_response": response,
                "command_error": error,
            }
        )
        rec = self.sudo().create(vals)
        rec._command_finished()
        return rec

    def _command_finished(self):
        """Triggered when command is finished
        Inherit to implement your own hooks
        """
        # Trigger next flightplan line
        for rec in self:
            context_timestamp = fields.Datetime.context_timestamp(
                self, fields.Datetime.now()
            )
            if rec.plan_log_id:  # type: ignore
                rec.plan_log_id._plan_command_finished(rec)  # type: ignore
            elif rec.command_status == 0:
                rec.create_uid.notify_success(
                    message=_(
                        "%(timestamp)s<br/>" "Command '%(name)s' finished successfully",
                        name=rec.command_id.name,
                        timestamp=context_timestamp,
                    ),
                    title=rec.server_id.name,
                    sticky=True,
                )
            else:
                rec.create_uid.notify_danger(
                    message=_(
                        "%(timestamp)s<br/>"
                        "Command '%(name)s'"
                        " finished with error. "
                        "Please check the command log for details.",
                        name=rec.command_id.name,
                        timestamp=context_timestamp,
                    ),
                    title=rec.server_id.name,
                    sticky=True,
                )
