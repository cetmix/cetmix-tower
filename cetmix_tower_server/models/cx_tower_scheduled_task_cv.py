from odoo import api, fields, models


class CxTowerScheduledTaskCv(models.Model):
    """
    Custom variable values for scheduled tasks.
    """

    _name = "cx.tower.scheduled.task.cv"
    _description = "Custom variable values for scheduled tasks"

    scheduled_task_id = fields.Many2one(
        "cx.tower.scheduled.task",
        string="Scheduled Task",
        required=True,
        ondelete="cascade",
    )
    variable_id = fields.Many2one(
        "cx.tower.variable",
        string="Variable",
        required=True,
    )
    variable_type = fields.Selection(related="variable_id.variable_type", readonly=True)
    value_char = fields.Char(
        string="Value",
        compute="_compute_value_char",
        readonly=False,
        store=True,
    )
    option_id = fields.Many2one(
        "cx.tower.variable.option",
        string="Option",
        domain="[('variable_id', '=', variable_id)]",
    )

    @api.depends("option_id", "variable_id", "variable_type")
    def _compute_value_char(self):
        """
        Compute value_char based on variable type and option selection.
        For option-type variables: sync value_char with selected option.
        For other types: leave value_char untouched (user input).
        """
        for rec in self:
            if rec.variable_type == "o":
                rec.value_char = rec.option_id.value_char if rec.option_id else ""

    @api.onchange("variable_id")
    def _onchange_variable_id(self):
        """
        Reset option_id when variable changes.
        """
        self.update({"option_id": None})
