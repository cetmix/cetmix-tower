# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models


class CxTowerPlanLine(models.Model):
    _name = "cx.tower.plan.line"
    _order = "sequence, plan_id"
    _description = "Cetmix Tower Flight Plan Line"

    def _selection_type(self):
        """Available actions to be executed by the line.
        Override when implementing your custom options.

        Returns:
            List of tuples:  `Selection` field option.
        """
        return [("command", "Run command"), ("file", "Push file")]

    active = fields.Boolean(related="plan_id.active", store=True, readonly=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(compute="_compute_name", readonly=True, store=True)
    plan_id = fields.Many2one(
        string="Flight Plan", comodel_name="cx.tower.plan", auto_join=True
    )
    type = fields.Selection(
        selection=lambda self: self._selection_type(),
        required=True,
        default=lambda self: self._selection_type()[0][0],
    )
    command_id = fields.Many2one(comodel_name="cx.tower.command")
    use_sudo = fields.Boolean(
        help="Will use sudo based on server settings."
        "If no sudo is configured will run without sudo"
    )
    file_template_id = fields.Many2one(comodel_name="cx.tower.file.template")
    action_ids = fields.One2many(
        string="Actions",
        comodel_name="cx.tower.plan.line.action",
        inverse_name="line_id",
        auto_join=True,
        help="Actions trigger based on command result."
        " If empty next command will be executed",
    )
    command_code = fields.Text(related="command_id.code", readonly=True)

    @api.depends("type", "command_id.name", "file_template_id.name")
    def _compute_name(self):
        """Line name is composed from line type and command or template name."""
        for line in self:
            if line.type == "command" and line.command_id:
                line.name = _("Run command `%(cmd)s`", cmd=line.command_id.name)
            elif line.type == "file" and line.file_template_id:
                line.name = _(
                    "Push file using `%(file)s`", file=line.file_template_id.name
                )
            else:
                line.name = _("...")

    def _execute(self, server, plan_log_record, **kwargs):
        """Execute command from the Flight Plan line

        Args:
            server (cx.tower.server()): Server object
            plan_log_record (cx.tower.plan.log()): Log record object
            kwargs (dict): Optional arguments
                Following are supported but not limited to:
                    - "plan_log": {values passed to flightplan logger}
                    - "log": {values passed to logger}
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

        server.execute_commands(self.command_id, use_sudo, **kwargs)
