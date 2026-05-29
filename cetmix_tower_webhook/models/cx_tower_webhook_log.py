# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import timedelta

from odoo import api, fields, models
from odoo.http import request


class CxTowerWebhookLog(models.Model):
    """Webhook Call Log"""

    _name = "cx.tower.webhook.log"
    _description = "Webhook Call Log"
    _order = "create_date desc"
    _rec_name = "display_name"

    webhook_id = fields.Many2one(
        comodel_name="cx.tower.webhook",
        ondelete="cascade",
        index=True,
        help="Webhook that received the call.",
    )
    endpoint = fields.Char(
        readonly=True,
    )
    authenticator_id = fields.Many2one(
        comodel_name="cx.tower.webhook.authenticator",
        readonly=True,
    )
    request_method = fields.Selection(
        [
            ("post", "POST"),
            ("get", "GET"),
        ],
        default="post",
        required=True,
        help="Select the HTTP method for this webhook.",
    )
    request_headers = fields.Text(
        help="Headers of the received HTTP request (JSON-encoded).",
    )
    request_payload = fields.Text(
        help="Payload/body of the received HTTP request (JSON-encoded).",
    )
    authentication_status = fields.Selection(
        [
            ("success", "Success"),
            ("failed", "Failed"),
            ("not_required", "Not Required"),
        ],
        required=True,
        default="failed",
        help="Result of authentication for this webhook call.",
    )
    code_status = fields.Selection(
        [
            ("success", "Success"),
            ("failed", "Failed"),
            ("skipped", "Skipped"),
        ],
        string="Webhook Code Status",
        required=True,
        default="skipped",
        help="Result of webhook code execution.",
    )
    http_status = fields.Integer(
        string="HTTP Status",
        help="HTTP status code returned to the client.",
    )
    result_message = fields.Text(
        help="Message returned by the webhook code or authenticator (if any).",
    )
    error_message = fields.Text(
        help="Error message in case of authentication or code failure.",
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Run as User",
        help="User as which the webhook code was executed (if set).",
    )
    ip_address = fields.Char(
        string="IP Address",
        help="IP address of the client that made the request.",
    )
    country_id = fields.Many2one(
        comodel_name="res.country",
        help="Country of the client that made the request.",
    )
    display_name = fields.Char(
        compute="_compute_display_name",
        store=True,
        readonly=True,
    )

    @api.depends("webhook_id", "endpoint", "http_status")
    def _compute_display_name(self):
        """Compute display name."""
        for rec in self:
            rec.display_name = (
                f"{rec.webhook_id.display_name or ''} ({rec.endpoint}) "
                f"[{rec.http_status or ''}]"
            )

    @api.model
    def _get_country_id(self):
        """
        Return the country ID of the client based on geoip information.

        Returns:
            int | bool: Country ID if found, otherwise False.
        """
        country_code = None
        if request and hasattr(request, "geoip") and request.geoip:
            country_code = request.geoip.get("country_code")
        if country_code:
            country = (
                self.env["res.country"]
                .sudo()
                .search([("code", "=", country_code)], limit=1)
            )
            if country:
                return country.id
        return False

    @api.model
    def _get_ip_address(self):
        """
        Return the IP address of the client making the request.

        Returns:
            str | None: IP address string, or None if unavailable.
        """
        if not request:
            return None
        # Check for forwarded IP (common proxy headers)
        forwarded_for = request.httprequest.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Return the first IP in the chain
            return forwarded_for.split(",")[0].strip()
        return request.httprequest.remote_addr

    @api.model
    def create_from_call(self, **kwargs):
        """
        Create a log entry from webhook call parameters.

        Args:
            **kwargs: Values passed to `_prepare_values`.

        Returns:
            CxTowerWebhookLog: Newly created log record.
        """
        values = self._prepare_values(**kwargs)
        return self.create(values)

    @api.model
    def _prepare_values(self, webhook=None, **kwargs):
        """
        Prepare values for creating a webhook log record.

        Args:
            webhook (RecordSet, optional): Webhook record.
            **kwargs: Additional fields such as endpoint, request_method, etc.

        Returns:
            dict: Prepared values for log creation.
        """
        vals = {
            "webhook_id": webhook.id if webhook else None,
            "endpoint": webhook.endpoint if webhook else kwargs.get("endpoint"),
            "authenticator_id": webhook.authenticator_id.id if webhook else None,
            "request_method": webhook.method
            if webhook
            else kwargs.get("request_method"),
            "user_id": webhook.user_id.id if webhook else None,
            "ip_address": self._get_ip_address(),
            "country_id": self._get_country_id(),
            **kwargs,
        }
        return vals

    @api.autovacuum
    def _gc_delete_old_logs(self):
        """
        Remove old webhook log records beyond configured retention period.

        This method is automatically triggered by Odoo's autovacuum.
        """
        days = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("cetmix_tower_webhook.webhook_log_duration", 30)
        )
        cutoff = fields.Datetime.now() - timedelta(days=days)
        logs_to_delete = self.sudo().search([("create_date", "<", cutoff)])
        logs_to_delete.unlink()
