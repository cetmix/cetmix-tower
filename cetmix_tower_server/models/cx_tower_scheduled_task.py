import logging
from datetime import timedelta

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class CxTowerScheduledTask(models.Model):
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
                        "next_call": self._get_next_call(task, finished_at),
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
        """
        num = task.interval_number or 1
        intervals = {
            "minutes": timedelta(minutes=num),
            "hours": timedelta(hours=num),
            "days": timedelta(days=num),
            "weeks": timedelta(weeks=num),
            "months": relativedelta(months=num),
        }
        return from_date + intervals.get(task.interval_type, timedelta())

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
        for server in self.server_ids:
            server.run_command(self.command_id, **kwargs)

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

        for server in self.server_ids:
            server.run_flight_plan(self.plan_id, **kwargs)

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
