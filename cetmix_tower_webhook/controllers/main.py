# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json
import logging

from odoo import http
from odoo.http import Response, request

_logger = logging.getLogger(__name__)


class CetmixTowerWebhookController(http.Controller):
    """
    Handles incoming requests to Tower webhooks.
    """

    @http.route(
        ["/cetmix_tower_webhooks/<string:endpoint>"],
        type="http",
        auth="public",
        methods=["POST", "GET"],
        csrf=False,
        save_session=False,
    )
    def cetmix_webhook(self, endpoint, **kwargs):
        """
        Process an incoming webhook request.

        Workflow:
            1. Extract request headers, body, and HTTP method.
            2. Match the request against a registered webhook.
            3. Authenticate the request if required.
            4. Execute the webhook code.
            5. Log the request and return the response.

        Args:
            endpoint (str): The requested webhook endpoint.
            **kwargs: Additional request parameters.

        Returns:
            Response: HTTP JSON response containing the result message.
        """
        # Step 1: Extract request data
        headers = self._extract_webhook_request_headers()
        raw_data = self._extract_webhook_request_raw_data()
        http_method = request.httprequest.method.lower()

        # Step 2. Find webhook
        webhook = (
            request.env["cx.tower.webhook"]
            .sudo()
            .search(
                [
                    ("endpoint", "=", endpoint),
                    ("method", "=", http_method),
                    ("active", "=", True),
                ],
            )
        )
        payload = self._extract_webhook_request_payload(webhook)

        log_model = request.env["cx.tower.webhook.log"].sudo()
        log_values = log_model._prepare_values(
            webhook=webhook,
            endpoint=endpoint,
            request_method=http_method,
            request_payload=payload,
            request_headers=headers,
            authentication_status="not_required",
            code_status="skipped",
        )

        if not webhook:
            log_values.update(
                {
                    "authentication_status": "failed",
                    "http_status": 404,
                }
            )
            return self._finalize_webhook_response(
                message="Webhook not found",
                error_message="Webhook not found",
                **log_values,
            )

        # Step 3. Authenticate
        auth_status, auth_error, http_auth_code = "success", None, 200
        if webhook.authenticator_id:
            if not webhook.authenticator_id.is_ip_allowed(self._get_remote_addr()):
                auth_status, auth_error, http_auth_code = (
                    "failed",
                    "Address not allowed",
                    403,
                )
                log_values.update(
                    {
                        "error_message": auth_error,
                        "http_status": http_auth_code,
                        "authentication_status": auth_status,
                    }
                )
                return self._finalize_webhook_response(
                    message=auth_error,
                    **log_values,
                )

            try:
                with request.env.cr.savepoint():
                    auth_result = webhook.authenticator_id.sudo().authenticate(
                        headers=headers,
                        raw_data=raw_data,
                        payload=payload,
                    )
                    if not auth_result.get("allowed"):
                        raise Exception(
                            auth_result.get("message", "Authentication not allowed")
                        )
            except Exception as e:
                auth_status, auth_error, http_auth_code = "failed", str(e), 403
        else:
            auth_status = "not_required"

        if auth_status == "failed":
            # Authentication failed
            log_values.update(
                {
                    "error_message": auth_error,
                    "http_status": http_auth_code,
                    "authentication_status": auth_status,
                }
            )
            return self._finalize_webhook_response(
                message=auth_error,
                **log_values,
            )

        # Step 4. Execute webhook code
        code_status, error_message, http_code, message = "success", None, 200, "OK"
        try:
            with request.env.cr.savepoint():
                code_result = webhook.execute(payload, headers=headers)
            if code_result.get("exit_code") != 0:
                raise Exception(code_result.get("message"))
            message = code_result.get("message") or "OK"
        except Exception as e:
            code_status, error_message, http_code, message = "failed", str(e), 500, None

        # Step 5. Update log
        log_values.update(
            {
                "code_status": code_status,
                "error_message": error_message,
                "http_status": http_code,
                "result_message": message,
                "authentication_status": auth_status,
            }
        )

        return self._finalize_webhook_response(
            message=message or error_message or "", **log_values
        )

    def _extract_webhook_request_payload(self, webhook):
        """
        Extract the request payload depending on HTTP method and content type.

        Args:
            webhook (cx.tower.webhook): Webhook record with configuration
                (may be empty).

        Returns:
            dict: Parsed payload as a dictionary. Empty if parsing fails.
        """
        http_method = request.httprequest.method
        try:
            if http_method.upper() == "POST":
                content_type = webhook.content_type if webhook else "json"
                return self._get_payload_by_content_type(content_type)
            elif http_method.upper() == "GET":
                return request.httprequest.args.to_dict(flat=True)
        except Exception:
            return {}
        return {}

    def _get_payload_by_content_type(self, content_type):
        """
        Return the request payload for POST requests according to content type.

        Args:
            content_type (str): Payload format, e.g. "json" or "form".

        Returns:
            dict: Parsed payload as a dictionary.
        """
        if content_type == "form":
            return request.httprequest.form.to_dict(flat=True)
        data = request.httprequest.data
        return json.loads(data or "{}") if data else {}

    def _extract_webhook_request_headers(self):
        """
        Extract request headers.

        Returns:
            dict: Request headers as a dictionary.
        """
        return dict(request.httprequest.headers)

    def _extract_webhook_request_raw_data(self):
        """
        Return raw request body.

        Returns:
            bytes: Raw HTTP request body.
        """
        return request.httprequest.data

    def _finalize_webhook_response(self, message, **kwargs):
        """
        Create a log entry and return final HTTP response.

        Args:
            message (str): Response message text.
            **kwargs: Log values for `cx.tower.webhook.log`.

        Returns:
            Response: HTTP JSON response with message and status code.
        """
        try:
            with request.env.cr.savepoint():
                request.env["cx.tower.webhook.log"].sudo().create_from_call(**kwargs)
        except Exception:
            # don't break controller if logging fails
            _logger.error("Failed to create log entry", exc_info=True)

        return Response(
            status=kwargs.get("http_status") or 200,
            response=json.dumps({"message": message or ""}),
            content_type="application/json",
        )

    def _get_remote_addr(self):
        """
        Return the remote IP address of the current request.

        Returns:
            str: Remote client IP address.
        """
        return request.httprequest.remote_addr
