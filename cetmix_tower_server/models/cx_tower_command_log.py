# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from ansi2html import Ansi2HTMLConverter

from odoo import _, api, fields, models, tools
from odoo.service.model import PG_CONCURRENCY_EXCEPTIONS_TO_RETRY

from .constants import COMMAND_STOPPED, GENERAL_ERROR

html_converter = Ansi2HTMLConverter(inline=True)
_logger = logging.getLogger(__name__)


class CxTowerCommandLog(models.Model):
    """Command execution log"""

    _name = "cx.tower.command.log"
    _description = "Cetmix Tower Command Log"
    _order = "start_date desc, id desc"

    active = fields.Boolean(default=True)
    name = fields.Char(compute="_compute_name", store=True)
    label = fields.Char(
        help="Custom label. Can be used for search/tracking",
        index="trigram",
    )
    server_id = fields.Many2one(
        comodel_name="cx.tower.server", required=True, index=True, ondelete="cascade"
    )
    jet_template_id = fields.Many2one(
        comodel_name="cx.tower.jet.template",
        index=True,
        ondelete="cascade",
        compute="_compute_jet_id",
        store=True,
        readonly=False,
    )
    jet_id = fields.Many2one(
        comodel_name="cx.tower.jet",
        index=True,
        ondelete="cascade",
        compute="_compute_jet_id",
        store=True,
        readonly=False,
    )
    waypoint_id = fields.Many2one(
        comodel_name="cx.tower.jet.waypoint",
        related="plan_log_id.waypoint_id",
        readonly=True,
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
        compute_sudo=True,
        help="For how long a flight plan is already running",
    )
    # -- Command
    is_running = fields.Boolean(
        help="Command is being executed right now",
        compute="_compute_duration",
        store=True,
    )
    command_id = fields.Many2one(
        comodel_name="cx.tower.command", required=True, index=True, ondelete="restrict"
    )
    access_level = fields.Selection(
        related="command_id.access_level",
        readonly=True,
        store=True,
        index=True,
    )

    command_action = fields.Selection(related="command_id.action", store=True)
    path = fields.Char(string="Execution Path", help="Where command was executed")
    code = fields.Text(string="Command Code", help="Command code that was executed")
    command_status = fields.Integer(
        string="Exit Code",
        help="0 if command finished successfully.\n"
        "-100 general error,\n"
        "-101 not found,\n"
        "-201 another instance of this command is running,\n"
        "-202 no runner found for the command action,\n"
        "-203 Python code execution failed,\n"
        "-205 plan line condition check failed,\n"
        "-206 command timed out,\n"
        "-207 command is not compatible with server,\n"
        "-208 command is stopped by user,\n"
        "503 if SSH connection error occurred",
    )
    command_response = fields.Text(string="Response")
    command_error = fields.Text(string="Error")
    command_result_html = fields.Html(
        compute="_compute_command_result_html",
        help="Result converted to HTML. Used for SSH commands.",
    )
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

    triggered_plan_command_log_ids = fields.One2many(
        comodel_name="cx.tower.command.log",
        inverse_name="plan_log_id",
        related="triggered_plan_log_id.command_log_ids",
        readonly=True,
        string="Triggered Flight Plan Commands",
    )
    scheduled_task_id = fields.Many2one(
        "cx.tower.scheduled.task",
        ondelete="set null",
        help="Scheduled task that triggered this command",
    )
    variable_values = fields.Json(
        default={},
        help="Custom variable values passed to the command",
    )

    @api.depends("server_id.name", "command_id.name")
    def _compute_name(self):
        for rec in self:
            rec.name = ": ".join((rec.server_id.name, rec.command_id.name))  # type: ignore

    @api.depends("plan_log_id")
    def _compute_jet_id(self):
        for command_log in self:
            if command_log.plan_log_id:
                command_log.update(
                    {
                        "jet_id": command_log.plan_log_id.jet_id,
                        "jet_template_id": command_log.plan_log_id.jet_template_id,
                    }
                )

    @api.depends("start_date", "finish_date")
    def _compute_duration(self):
        for command_log in self:
            if not command_log.start_date:
                command_log.is_running = False
                continue
            if not command_log.finish_date:
                command_log.is_running = True
                continue
            duration = (
                command_log.finish_date - command_log.start_date
            ).total_seconds()
            command_log.update(
                {
                    "duration": duration,
                    "is_running": False,
                }
            )

    @api.depends("is_running")
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

    @api.depends("command_response", "command_error")
    def _compute_command_result_html(self):
        for command_log in self:
            command_result = command_log.command_response or command_log.command_error
            if command_result:
                try:
                    command_log.command_result_html = html_converter.convert(
                        command_result
                    )
                except Exception as e:
                    _logger.error("Error converting command response to HTML: %s", e)
                    command_log.command_result_html = _(
                        "<p><strong>Error converting command"
                        " response to HTML: %(error)s</strong></p>",
                        error=e,
                    )
            else:
                command_log.command_result_html = False

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
            "start_date": start_date if start_date else fields.Datetime.now(),
        }
        # Apply kwargs
        vals.update(kwargs)
        log_record = self.sudo().create(vals)
        return log_record

    def stop(self):
        """
        Stop the command execution.

        If this command started a child flight plan that is still running,
        stop that plan first. The child plan's ``finish()`` then closes this
        command with ``PLAN_STOPPED`` when ``triggering_command_log_id`` is
        set. If that reverse link is missing, finish this command with
        ``COMMAND_STOPPED``. Do not force-stop the parent plan: line
        actions decide.
        """
        user_name = self.env.user.name
        for log in self:
            if not log.is_running:
                continue

            if log.triggered_plan_log_id and log.triggered_plan_log_id.is_running:
                log.triggered_plan_log_id.stop()
                log.invalidate_recordset(
                    ["is_running", "finish_date", "command_status"]
                )
                # 7.3 should have closed this command. Close it here when
                # the reverse link is missing. Do not stop plan_log_id:
                # line actions decide.
                if log.is_running:
                    log.finish(
                        status=COMMAND_STOPPED,
                        error=_("Stopped by user %(user)s", user=user_name),
                    )
                continue

            log.finish(
                status=COMMAND_STOPPED,
                error=_("Stopped by user %(user)s", user=user_name),
            )

            # Ensure flight plan log is stopped too
            if log.plan_log_id and log.plan_log_id.is_running:
                log.plan_log_id.stop()

    def finish(
        self, finish_date=None, status=None, response=None, error=None, **kwargs
    ):
        """Save final command result when command is finished.

        Can be called for multiple command logs at once.

        Idempotent: logs that already have ``finish_date`` are skipped.
        ``is_running`` also requires ``start_date``, so it cannot be the
        unfinished check (Integer ``command_status`` 0 is both unset and
        success). Concurrent callers that lose ``FOR UPDATE NOWAIT`` (or
        hit serialization/deadlock) are skipped without raising so a batch
        zombie cron can continue.

        After a successful write, if ``command_status`` is 0 and the command
        has ``server_status``, that status is written once per server. If
        several logs share a server and disagree on ``server_status``, the
        last log in the recordset wins.

        Args:
            finish_date (datetime) command finish date time.
            status (int, optional): command execution status. Defaults to None.
            response (Char, optional): Command response. Defaults to None.
            error (Char, optional): Command error. Defaults to None.
            **kwargs (dict): optional values
        """
        unfinished_logs = self.filtered(lambda rec: not rec.finish_date)
        if not unfinished_logs:
            return

        locked_logs = self.browse()
        for command_log in unfinished_logs:
            try:
                with self.env.cr.savepoint(), tools.mute_logger("odoo.sql_db"):
                    self.env.cr.execute(
                        (
                            f"SELECT finish_date FROM {self._table}"
                            " WHERE id = %s FOR UPDATE NOWAIT"
                        ),
                        (command_log.id,),
                    )
                    row = self.env.cr.fetchone()
                    if row and row[0]:
                        continue
                    locked_logs |= command_log
            except PG_CONCURRENCY_EXCEPTIONS_TO_RETRY as err:
                _logger.warning(
                    "Could not acquire lock on command log %s, skipping: %s",
                    command_log.id,
                    err,
                )
                continue

        if not locked_logs:
            return

        self_with_sudo = locked_logs.sudo()

        now = fields.Datetime.now()
        date_finish = finish_date if finish_date else now
        command_status = GENERAL_ERROR if status is None else status

        vals = {
            "finish_date": date_finish,
            "command_status": command_status,
            "command_response": response,
            "command_error": error,
        }

        vals.update(kwargs)
        self_with_sudo.write(vals)

        if vals.get("command_status") == 0:
            server_status_by_id = {}
            for command_log in self_with_sudo:
                if command_log.command_id.server_status:
                    server_status_by_id[command_log.server_id.id] = (
                        command_log.server_id,
                        command_log.command_id.server_status,
                    )
            for server, new_status in server_status_by_id.values():
                server.write({"status": new_status})

        for command_log in self_with_sudo:
            command_log._command_finished()

    def record(
        self,
        server_id,
        command_id,
        start_date=None,
        finish_date=None,
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
        now = fields.Datetime.now()
        vals.update(
            {
                "server_id": server_id,
                "command_id": command_id,
                "start_date": start_date or now,
                "finish_date": finish_date or now,
                "command_status": status,
                "command_response": response,
                "command_error": error,
            }
        )
        rec = self.sudo().create(vals)
        rec._command_finished()
        return rec

    def _command_finished(self):
        """Triggered when command is finished.

        Inherit to implement your own hooks. Extenders that need to cancel
        an external job on COMMAND_STOPPED / COMMAND_TIMED_OUT should
        inspect ``command_status``, then call ``super()``. Core ``stop()``
        already goes through ``finish()``.

        Returns:
            bool: True if event was handled
        """

        self.ensure_one()

        # Do not notify if command is run from a Flight Plan.
        if self.plan_log_id:  # type: ignore
            self.plan_log_id._plan_command_finished(self)  # type: ignore
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
            "cetmix_tower_server.action_cx_tower_command_log"
        )

        context = self.env.context.copy()
        params = dict(context.get("params") or {})
        params["button_name"] = _("View Log")
        context["params"] = params
        action.update(
            {
                "views": [(False, "form")],
                "context": context,
                "res_id": self.id,
            }
        )

        # Send notification
        if self.command_status == 0 and notification_type_success:
            # Success notification
            self.create_uid.notify_success(
                message=_(
                    "%(timestamp)s<br/>" "Command '%(name)s' finished successfully",
                    name=self.command_id.name,
                    timestamp=context_timestamp,
                ),
                title=self.server_id.name,
                sticky=notification_type_success == "sticky",
                action=action,
            )

        # Error notification
        if self.command_status != 0 and notification_type_error:
            self.create_uid.notify_danger(
                message=_(
                    "%(timestamp)s<br/>" "Command '%(name)s' finished with error",
                    name=self.command_id.name,
                    timestamp=context_timestamp,
                ),
                title=self.server_id.name,
                sticky=notification_type_error == "sticky",
                action=action,
            )

        return True
