from odoo import fields, models


class CxTowerServerMetrics(models.Model):
    _name = "cx.tower.server.metrics"
    _description = "Server Resource Metrics"
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

    # RAM (in MB)
    ram_total_mb = fields.Float(string="RAM Total (MB)")
    ram_used_mb = fields.Float(string="RAM Used (MB)")
    ram_free_mb = fields.Float(string="RAM Free (MB)")

    # Disk (in GB)
    disk_total_gb = fields.Float(string="Disk Total (GB)")
    disk_used_gb = fields.Float(string="Disk Used (GB)")
    disk_free_gb = fields.Float(string="Disk Free (GB)")

    # CPU
    cpu_percent = fields.Float(string="CPU Usage (%)")
    cpu_cores = fields.Integer(string="CPU Cores", default=1)

    source = fields.Selection(
        selection=[
            ("pull", "Pull (SSH)"),
            ("push", "Push (Webhook)"),
        ],
        default="pull",
        required=True,
    )
