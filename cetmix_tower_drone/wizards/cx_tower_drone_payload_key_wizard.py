# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class CxTowerDronePayloadKeyWizard(models.TransientModel):
    """Show a freshly generated payload key so it can be copied."""

    _name = "cx.tower.drone.payload.key.wizard"
    _description = "Show Generated Payload Key"

    controller_id = fields.Many2one(
        comodel_name="cx.tower.drone.controller",
        required=True,
        ondelete="cascade",
    )
    payload_key = fields.Char(compute="_compute_payload_key")

    @api.depends_context("default_payload_key")
    def _compute_payload_key(self):
        """Read the key from the action that opened this dialog.

        The generate action puts the Fernet key in the context. The form
        sends that context when it reads the wizard, so the key is shown
        once and is not written to the transient table.

        """
        key = self.env.context.get("default_payload_key") or False
        for wizard in self:
            wizard.payload_key = key
