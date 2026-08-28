from odoo import fields, models


class CxTowerServerAlert(models.Model):
    _name = "cx.tower.server.alert"
    _description = "Server Resource Alert"
    _order = "timestamp desc"

    server_id = fields.Many2one(
        comodel_name="cx.tower.server",
        string="Server",
        required=True,
        ondelete="cascade",
    )
    timestamp = fields.Datetime(
        default=fields.Datetime.now,
        required=True,
    )
    resource = fields.Selection(
        selection=[
            ("cpu", "CPU"),
            ("ram", "RAM"),
            ("disk", "Disk"),
        ],
        required=True,
    )
    value = fields.Float()
    threshold = fields.Float()
    resolved = fields.Boolean(default=False)
