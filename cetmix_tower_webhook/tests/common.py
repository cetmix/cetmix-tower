# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase


class CetmixTowerWebhookCommon(TransactionCase):
    def setUp(self):
        super().setUp()

        # Set base url for correct link generation
        self.web_base_url = "https://example.com"
        self.env["ir.config_parameter"].sudo().set_param(
            "web.base.url", self.web_base_url
        )

        # Create simple authenticator that allows all requests
        self.WebhookAuthenticator = self.env["cx.tower.webhook.authenticator"]
        self.simple_authenticator = self.WebhookAuthenticator.create(
            {
                "name": "Simple Authenticator",
                "code": "result = {'allowed': True, 'message': 'OK'}",
            }
        )

        # Create Simple Webhook
        self.Webhook = self.env["cx.tower.webhook"]
        self.simple_webhook = self.Webhook.create(
            {
                "name": "Simple Webhook",
                "endpoint": "simple_webhook",
                "code": "result = {'exit_code': 0, 'message': 'OK'}",
                "authenticator_id": self.simple_authenticator.id,
            }
        )

        # Log model
        self.Log = self.env["cx.tower.webhook.log"]
