# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerVariable(models.Model):
    _inherit = "cx.tower.variable"

    # --- Link to records where the variable is used
    webhook_ids = fields.Many2many(
        comodel_name="cx.tower.webhook",
        relation="cx_tower_webhook_variable_rel",
        column1="variable_id",
        column2="webhook_id",
        copy=False,
    )
    webhook_ids_count = fields.Integer(
        string="Webhook Count", compute="_compute_webhook_ids_count"
    )
    webhook_authenticator_ids = fields.Many2many(
        comodel_name="cx.tower.webhook.authenticator",
        relation="cx_tower_webhook_authenticator_variable_rel",
        column1="variable_id",
        column2="webhook_authenticator_id",
        copy=False,
    )
    webhook_authenticator_ids_count = fields.Integer(
        string="Webhook Authenticator Count", compute="_compute_webhook_ids_count"
    )

    def _compute_webhook_ids_count(self):
        """
        Count number of webhooks and webhook authenticators for the variable
        """
        for rec in self:
            rec.update(
                {
                    "webhook_ids_count": len(rec.webhook_ids),
                    "webhook_authenticator_ids_count": len(
                        rec.webhook_authenticator_ids
                    ),
                }
            )

    def action_open_webhooks(self):
        """Open the webhooks where the variable is used"""

        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "cetmix_tower_webhook.cx_tower_webhook_action"
        )
        action.update(
            {
                "domain": [("variable_ids", "in", self.ids)],
            }
        )
        return action

    def action_open_webhook_authenticators(self):
        """Open the webhook authenticators where the variable is used"""

        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "cetmix_tower_webhook.cx_tower_webhook_authenticator_action"
        )
        action.update(
            {
                "domain": [("variable_ids", "in", self.ids)],
            }
        )
        return action

    def _get_propagation_field_mapping(self):
        """
        Override to add webhook and webhook authenticator
        to the propagation field mapping.
        """
        res = super()._get_propagation_field_mapping()
        res.update(
            {
                "cx.tower.webhook": ["code"],
                "cx.tower.webhook.authenticator": ["code"],
            }
        )
        return res
