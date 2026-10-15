from odoo import fields, models


class CxTowerScheduledTaskCv(models.Model):
    """
    Custom variable values for scheduled tasks.
    """

    _inherit = "cx.tower.custom.variable.value.mixin"
    _name = "cx.tower.scheduled.task.cv"
    _description = "Custom variable values for scheduled tasks"

    # The reference mixin marks name required. A scheduled task line has no name.
    # We don't need to store it either
    name = fields.Char(required=False, store=False)
    scheduled_task_id = fields.Many2one(
        "cx.tower.scheduled.task",
        string="Scheduled Task",
        required=True,
        ondelete="cascade",
    )
