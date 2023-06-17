from odoo import fields, models

from .constants import PLAN_IS_EMPTY


class CxTowerPlanLog(models.Model):
    _name = "cx.tower.plan.log"
    _description = "Cetmix Tower Flightplan Log"
    _order = "start_date desc, id desc"

    name = fields.Char(compute="_compute_name", compute_sudo=True)
    label = fields.Char(help="Custom label. Can be used for search/tracking")
    server_id = fields.Many2one(comodel_name="cx.tower.server")
    plan_id = fields.Many2one(string="Flightplan", comodel_name="cx.tower.plan")

    # -- Time
    start_date = fields.Datetime(string="Started")
    finish_date = fields.Datetime(string="Finished")
    duration = fields.Float(
        string="Duration, sec", help="Time consumed for execution, seconds"
    )
    # -- Commands
    is_running = fields.Boolean(help="Plan is being executed right now")
    plan_line_executed_id = fields.Many2one(
        comodel_name="cx.tower.plan.line",
        help="Flightplan line being currently executed",
    )
    command_log_ids = fields.One2many(
        comodel_name="cx.tower.command.log", inverse_name="plan_log_id"
    )
    plan_status = fields.Integer(string="Status")

    def _compute_name(self):
        for rec in self:
            rec.name = ": ".join((rec.server_id.name, rec.plan_id.name))  # type: ignore

    def start(self, server, plan, start_date=None, **kwargs):
        """Runs plan on server
        Creates initial log record when command is started.

        Args:
            server (cx.tower.server()) server.
            plan (cx.tower.plan()) Flightplan.
            start_date (datetime) command start date time.
            **kwargs (dict): optional values
                Following keys are supported but not limited to:
                - "plan_log": {values passed to flightplan logger}
                - "log": {values passed to logger}
                - "key": {values passed to key parser}
        Returns:
            (cx.tower.plan.log()) new flightplan log record or False
        """

        vals = {
            "server_id": server.id,
            "plan_id": plan.id,
            "is_running": True,
            "start_date": start_date if start_date else fields.Datetime.now(),
        }
        # Extract and apply plan log kwargs
        if kwargs:
            plan_log_kwargs = kwargs.get("plan_log")
            if plan_log_kwargs:
                vals.update(plan_log_kwargs)

        # Get plan line to be executed first or finish with error if empty
        if not plan.line_ids:
            vals.update(
                {
                    "is_running": False,
                    "finish_date": fields.Datetime.now(),
                    "duration": 0,
                    "plan_status": PLAN_IS_EMPTY,
                }
            )
            proceed = False
        else:
            proceed = True

        plan_log = self.sudo().create(vals)

        # Run the first line
        if proceed:
            plan.line_ids[0]._execute(server, plan_log, **kwargs)

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
        return

    def _plan_command_finished(self, command_log):
        """This function is triggered when a command from this log is finished.
        Next action is triggered based on command status (ak exit code)

        Args:
            command_log (cx.tower.command.log()): Command log object

        """
        self.ensure_one()

        # Get next line to execute
        self.plan_id._run_next_action(command_log)  # type: ignore
