import logging
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class CxTowerScheduledTask(models.Model):
    """
    Scheduled Tasks.
    Used to schedule commands and flight plans to run on servers and jets.
    """

    _name = "cx.tower.scheduled.task"
    _description = "Scheduled Task"
    _inherit = ["cx.tower.access.role.mixin", "cx.tower.reference.mixin"]
    _order = "sequence, next_call"

    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    server_ids = fields.Many2many(
        "cx.tower.server",
        "cx_tower_scheduled_task_server_rel",
        "scheduled_task_id",
        "server_id",
        string="Servers",
    )
    server_template_ids = fields.Many2many(
        string="Server Templates",
        comodel_name="cx.tower.server.template",
        relation="cx_tower_server_template_scheduled_task_rel",
        column1="scheduled_task_id",
        column2="server_template_id",
    )
    jet_ids = fields.Many2many(
        "cx.tower.jet",
        "cx_tower_scheduled_task_jet_rel",
        "scheduled_task_id",
        "jet_id",
        string="Jets",
    )
    jet_template_ids = fields.Many2many(
        string="Jet Templates",
        comodel_name="cx.tower.jet.template",
        relation="cx_tower_jet_template_scheduled_task_rel",
        column1="scheduled_task_id",
        column2="jet_template_id",
    )
    action = fields.Selection(
        [("command", "Command"), ("plan", "Flight Plan")], required=True
    )
    command_id = fields.Many2one("cx.tower.command", string="Command")
    plan_id = fields.Many2one(string="Flight Plan", comodel_name="cx.tower.plan")
    is_running = fields.Boolean(default=False, readonly=True)
    interval_number = fields.Integer(default=1, help="Repeat every x.")
    interval_type = fields.Selection(
        [
            ("minutes", "Minutes"),
            ("hours", "Hours"),
            ("days", "Days"),
            ("dow", "Days of Week"),
            ("weeks", "Weeks"),
            ("months", "Months"),
        ],
        string="Interval Unit",
        default="months",
    )
    next_call = fields.Datetime(
        string="Next Execution Date",
        required=True,
        default=fields.Datetime.now,
        help="Next planned execution date for this task.",
    )
    last_call = fields.Datetime(
        string="Last Execution Date", help="Previous time the task ran successfully."
    )
    # Days of week
    monday = fields.Boolean()
    tuesday = fields.Boolean()
    wednesday = fields.Boolean()
    thursday = fields.Boolean()
    friday = fields.Boolean()
    saturday = fields.Boolean()
    sunday = fields.Boolean()

    custom_variable_value_ids = fields.One2many(
        "cx.tower.scheduled.task.cv",
        "scheduled_task_id",
        string="Custom Variable Values",
    )
    warning_message = fields.Text(
        compute="_compute_warning_message",
    )

    # ---- Access. Add relation for mixin fields
    user_ids = fields.Many2many(
        relation="cx_tower_scheduled_task_user_rel",
    )
    manager_ids = fields.Many2many(
        relation="cx_tower_scheduled_task_manager_rel",
    )

    _sql_constraints = [
        (
            "interval_positive",
            "CHECK (interval_number > 0)",
            "Interval number must be greater than zero.",
        ),
    ]

    @api.constrains(
        "interval_type",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    )
    def _check_days_of_week(self):
        """
        Check if at least one day of week is selected
        """
        for task in self:
            if task.interval_type == "dow" and not any(
                [
                    task.monday,
                    task.tuesday,
                    task.wednesday,
                    task.thursday,
                    task.friday,
                    task.saturday,
                    task.sunday,
                ]
            ):
                raise ValidationError(
                    _(
                        "At least one day of week must be selected for the task '%s'.",
                        task.display_name,
                    )
                )

    @api.depends("interval_number", "interval_type")
    def _compute_warning_message(self):
        """
        Show warning on the task form if interval in the scheduled task
        is less than interval in the underlaying cron job.
        """
        cron = self.env.ref(
            "cetmix_tower_server.ir_cron_run_scheduled_tasks", raise_if_not_found=False
        )
        if not cron:
            self.warning_message = False
            return

        # Using now's date as the base point ensures a consistent and comparable
        # reference when calculating the next scheduled execution for both the cron
        # and the tasks.
        now = fields.Datetime.now()
        # _get_next_call is designed for tasks, but can also be used for the
        # cron record, as both share the same interval fields. This keeps interval
        # comparison logic consistent.
        cron_next = self._get_next_call(cron, now)

        for task in self:
            if task.interval_type == "dow":
                task.warning_message = False
                continue
            task_next = self._get_next_call(task, now)
            if task_next < cron_next:
                task.warning_message = _(
                    "The selected task interval is too low in relation to the general "
                    "system settings. This may lead to task execution delays."
                )
            else:
                task.warning_message = False

    def action_run(self):
        """
        Run scheduled action and reschedule next call.
        """
        return self._run()

    def action_open_command_logs(self):
        """
        Open current scheduled task command log records
        """
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_command_log"
        )
        action["domain"] = [("scheduled_task_id", "=", self.id)]  # pylint: disable=no-member
        return action

    def action_open_plan_logs(self):
        """
        Open current scheduled task flightplan log records
        """
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_plan_log"
        )
        action["domain"] = [("scheduled_task_id", "=", self.id)]  # pylint: disable=no-member
        return action

    @api.model
    def _run_scheduled_tasks(self):
        """
        Cron: finds due tasks and runs their actions (command/plan).
        Handles errors per-task and reserves tasks atomically to avoid double execution.
        """
        now = fields.Datetime.now()
        due_tasks = self.search(
            [
                ("next_call", "<=", now),
                ("active", "=", True),
                ("is_running", "=", False),
            ]
        )
        if not due_tasks:
            return

        due_tasks.with_context(from_cron=True)._run()

    def _run(self):
        """
        Run scheduled action and reschedule next call.
        """
        tasks = self._reserve_tasks()
        if not tasks:
            return

        if self.env.context.get("from_cron"):
            # WARNING: Explicit commit!
            # This commit is made **only** when called from cron (context["from_cron"]).
            # Reason: To atomically reserve scheduled tasks by setting is_running=True,
            # so that only one cron worker processes each task, even if multiple workers
            # pick up the cron job at the same time. Without this commit, the change
            # would not be visible to other transactions until the end of the cron
            # transaction, leading to a race condition and possible double execution.
            # Explicit commits are strongly discouraged in Odoo business logic and
            # should be used only with clear justification and in strictly controlled
            # contexts (like this cron scenario). Never add this commit for general
            # business flows!
            self.env.cr.commit()  # pylint: disable=invalid-commit

        errors = []
        for task in tasks:
            try:
                with self.env.cr.savepoint():
                    if task.action == "command" and task.command_id:
                        task._run_command()
                    elif task.action == "plan" and task.plan_id:
                        task._run_plan()
            except Exception as e:
                _logger.exception("Scheduled task %s failed: %s", task.id, e)

                task_error = _(
                    "Unable to run scheduled task '%(f)s'. Error: %(e)s",
                    f=task.display_name,
                    e=e,
                )
                errors.append(task_error)

            finally:
                finished_at = fields.Datetime.now()
                # Always update the scheduling, even if the task failed
                task.write(
                    {
                        "last_call": finished_at,
                        "next_call": self._get_next_call(task, task.next_call),
                        "is_running": False,
                    }
                )

        if errors:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Failure"),
                    "message": "\n".join(errors),
                },
            }

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": _("Scheduled tasks run successfully."),
            },
        }

    def _get_next_call(self, task, from_date):
        """
        Calculate next_call datetime

        task: cx.tower.scheduled.task
        from_date: datetime
        """
        if task.interval_type == "dow":
            return self._get_next_call_dow(task, from_date)

        num = task.interval_number or 1
        intervals = {
            "minutes": timedelta(minutes=num),
            "hours": timedelta(hours=num),
            "days": timedelta(days=num),
            "weeks": timedelta(weeks=num),
            "months": relativedelta(months=num),
        }
        return from_date + intervals.get(task.interval_type, timedelta())

    def _get_task_selected_days(self, task):
        """
        Get list of selected weekday numbers for a task

        task: cx.tower.scheduled.task
        Returns: list of weekday numbers (0=Monday, 6=Sunday)
        """
        selected_days = []
        if task.monday:
            selected_days.append(0)
        if task.tuesday:
            selected_days.append(1)
        if task.wednesday:
            selected_days.append(2)
        if task.thursday:
            selected_days.append(3)
        if task.friday:
            selected_days.append(4)
        if task.saturday:
            selected_days.append(5)
        if task.sunday:
            selected_days.append(6)
        return selected_days

    def _get_next_call_dow(self, task, from_date):
        """
        Calculate next_call datetime for days of week interval type

        task: cx.tower.scheduled.task
        from_date: datetime
        """
        # Days of week: find next selected day at the same time
        # weekday() returns 0=Monday, 6=Sunday
        selected_days = self._get_task_selected_days(task)
        if not selected_days:
            raise ValidationError(
                _(
                    "At least one day of week must be selected for the task '%s'.",
                    task.display_name,
                )
            )
        current_weekday = from_date.weekday()

        # Find next selected day (starting from tomorrow to get next occurrence)
        # Check days in current week first (after today)
        next_day = None
        for day in selected_days:
            if day > current_weekday:
                next_day = day
                break

        # If no day found in current week, take first day of next week
        if next_day is None:
            next_day = min(selected_days)
            days_ahead = (7 - current_weekday) + next_day
        else:
            days_ahead = next_day - current_weekday

        # Create new datetime with same time, on the next selected day
        next_date = from_date + timedelta(days=days_ahead)
        return next_date.replace(
            hour=from_date.hour,
            minute=from_date.minute,
            second=from_date.second,
            microsecond=from_date.microsecond,
        )

    def _run_command(self):
        """Run command on selected servers."""
        variable_values = {
            value.variable_id.reference: value.value_char
            for value in self.custom_variable_value_ids
        }
        kwargs = {
            "log": {"scheduled_task_id": self.id},
            "variable_values": variable_values,
        }
        # Run for servers
        for server in self.server_ids:
            server.run_command(self.command_id, **kwargs)
        # Run for jets
        for jet in self.jet_ids:
            jet.run_command(self.command_id, **kwargs)

    def _run_plan(self):
        """Run flight plan on selected servers."""
        variable_values = {
            value.variable_id.reference: value.value_char
            for value in self.custom_variable_value_ids
        }
        kwargs = {
            "plan_log": {"scheduled_task_id": self.id},
            "variable_values": variable_values,
        }
        # Run for servers
        for server in self.server_ids:
            server.run_flight_plan(self.plan_id, **kwargs)
        # Run for jets
        for jet in self.jet_ids:
            jet.run_flight_plan(self.plan_id, **kwargs)

    def _reserve_tasks(self, limit=None):
        """
        Atomically select and lock free tasks for processing.
        """
        sql = """
            SELECT id
            FROM cx_tower_scheduled_task
            WHERE is_running = FALSE AND id IN %s
            ORDER BY id
        """
        params = [tuple(self.ids)]
        if limit:
            sql += " LIMIT %s"
            params.append(limit)
        sql += " FOR UPDATE SKIP LOCKED"
        self.env.cr.execute(sql, tuple(params))

        task_ids = [row[0] for row in self.env.cr.fetchall()]
        if not task_ids:
            return self.browse()

        tasks = self.browse(task_ids)
        tasks.write({"is_running": True})
        return tasks
