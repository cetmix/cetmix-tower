# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import re

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import ValidationError

from .constants import DEFAULT_WEBHOOK_CODE, DEFAULT_WEBHOOK_CODE_HELP


class CxTowerWebhook(models.Model):
    """Webhook"""

    _name = "cx.tower.webhook"
    _inherit = [
        "cx.tower.webhook.eval.mixin",
    ]
    _description = "Webhook"

    active = fields.Boolean(
        default=True,
        string="Enabled",
    )
    authenticator_id = fields.Many2one(
        comodel_name="cx.tower.webhook.authenticator",
        required=True,
        help="Select an Authenticator used for this webhook",
    )
    endpoint = fields.Char(
        required=True,
        copy=False,
        help="Webhook endpoint. The complete URL will be "
        "<your_tower_url>/cetmix_tower_webhooks/<endpoint>",
    )
    full_url = fields.Char(
        compute="_compute_full_url",
        help="Full URL of the webhook",
    )
    method = fields.Selection(
        [
            ("post", "POST"),
            ("get", "GET"),
        ],
        default="post",
        required=True,
        help="Select the HTTP method for this webhook",
    )
    content_type = fields.Selection(
        [
            ("json", "JSON"),
            ("form", "Form URL-Encoded"),
        ],
        string="Payload Type",
        default="json",
        required=True,
        help="How the payload is expected to be sent to this webhook: "
        "as JSON body or as URL-encoded form data",
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Run as User",
        help="Select a user to run the webhook from behalf of. If not set, "
        "the webhook will run as the current user.\n"
        "CAREFUL! You must realise and understand what you are doing including "
        "all the possible consequences when selecting a specific user",
        default=SUPERUSER_ID,
        required=True,
        copy=False,
    )
    log_count = fields.Integer(
        compute="_compute_log_count",
    )
    variable_ids = fields.Many2many(
        comodel_name="cx.tower.variable",
        relation="cx_tower_webhook_variable_rel",
        column1="webhook_id",
        column2="variable_id",
    )

    _sql_constraints = [
        (
            "endpoint_method_uniq",
            "unique(endpoint, method)",
            "Endpoint and method must be unique!",
        ),
    ]

    def _compute_log_count(self):
        """Compute log count."""
        data = {
            webhook.id: count
            for webhook, count in self.env["cx.tower.webhook.log"]._read_group(
                domain=[("webhook_id", "in", self.ids)],
                groupby=["webhook_id"],
                aggregates=["__count"],
            )
        }
        for rec in self:
            rec.log_count = data.get(rec.id, 0)

    @api.depends("endpoint")
    def _compute_full_url(self):
        """Compute full URL."""
        base_url = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("web.base.url", "")
            .rstrip("/")
        )
        for rec in self:
            rec.full_url = f"{base_url}/cetmix_tower_webhooks/{rec.endpoint}"

    @api.constrains("endpoint")
    def _check_endpoint_format(self):
        """Validate endpoint format."""
        pattern = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_/-]*[A-Za-z0-9])?$")
        for rec in self:
            if rec.endpoint and not pattern.fullmatch(rec.endpoint):
                raise ValidationError(
                    _(
                        "Endpoint must start and end with a letter or digit, "
                        "and may contain underscores, dashes, and slashes in between"
                    )
                )

    def _default_eval_code(self):
        """
        Returns the default code for the webhook.
        """
        return _(DEFAULT_WEBHOOK_CODE)

    def _get_default_python_eval_code_help(self):
        """
        Returns the default code help for the webhook.
        """
        return _(DEFAULT_WEBHOOK_CODE_HELP)

    def _get_python_eval_odoo_objects(self, **kwargs):
        """
        Override to add custom Odoo objects.
        """
        res = {
            "headers": {
                "import": kwargs.get("headers"),
                "help": _("Dictionary of request headers"),
            },
            "payload": {
                "import": kwargs.get("payload"),
                "help": _(
                    "Dictionary containing the request payload "
                    "(JSON for POST, params for GET)"
                ),
            },
        }
        res.update(super()._get_python_eval_odoo_objects(**kwargs))
        return res

    def _get_fields_for_yaml(self):
        """Override to add fields to YAML export."""
        res = super()._get_fields_for_yaml()
        res += [
            "name",
            "active",
            "authenticator_id",
            "endpoint",
            "method",
            "code",
            "content_type",
            "variable_ids",
            "secret_ids",
        ]
        return res

    def execute(self, payload=None, raise_on_error=True, **kwargs):
        """
        Run the webhook code and return a validated result.
        Handles errors and checks result format.

        Args:
            payload (dict): The webhook payload. If not provided,
                the payload will be empty.
            raise_on_error (bool): Raise ValidationError on error if True.
            **kwargs: Additional keyword arguments.

        Returns:
            dict: {
                'exit_code': <int>,
                'message': <str>
            }
        """
        self.ensure_one()
        self_with_user = self.with_user(self.user_id)
        payload = payload or {}

        try:
            result = self_with_user._run_webhook_eval_code(
                self_with_user.code,
                context_extra={"payload": payload, "headers": kwargs.get("headers")},
                default_result={"exit_code": 0, "message": None},
            )
        except Exception as e:
            if raise_on_error:
                raise ValidationError(
                    _("Webhook code execution error: %(error)s", error=e)
                ) from e
            result = {
                "exit_code": 1,
                "message": str(e),
            }

        return result

    def action_view_logs(self):
        """Open logs related to this webhook."""
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_webhook.cx_tower_webhook_log_action"
        )
        action["domain"] = [("webhook_id", "=", self.id)]
        return action
