from odoo import fields, models


class CxTowerScheduledTaskCv(models.Model):
    """
    Custom variable values for scheduled tasks.
    """

    _inherit = "cx.tower.custom.variable.value.mixin"
    _name = "cx.tower.scheduled.task.cv"
    _description = "Custom variable values for scheduled tasks"

    scheduled_task_id = fields.Many2one(
        "cx.tower.scheduled.task",
        string="Scheduled Task",
        required=True,
        ondelete="cascade",
    )
