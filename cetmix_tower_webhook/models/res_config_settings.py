from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    cetmix_tower_webhook_log_duration = fields.Integer(
        string="Keep Webhook Logs for (days)",
        help="Set the number of days to keep webhook logs. "
        "Old logs will be deleted automatically.",
        default=30,
        config_parameter="cetmix_tower_webhook.webhook_log_duration",
    )
