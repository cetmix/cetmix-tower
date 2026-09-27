# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models

# Context keys the generate action uses. None of these are stored.
_CONTEXT_KEYS = (
    ("drone_api_key", "default_drone_api_key"),
    ("payload_key", "default_payload_key"),
    ("drone_response_key", "default_drone_response_key"),
    ("result_storage_key", "default_result_storage_key"),
)


class CxTowerDronePayloadKeyWizard(models.TransientModel):
    """Show freshly generated drone keys so they can be copied."""

    _name = "cx.tower.drone.payload.key.wizard"
    _description = "Show Generated Drone Keys"

    controller_id = fields.Many2one(
        comodel_name="cx.tower.drone.controller",
        required=True,
        ondelete="cascade",
    )
    drone_api_key = fields.Char(
        string="Drone API Key",
        compute="_compute_keys",
    )
    payload_key = fields.Char(compute="_compute_keys")
    drone_response_key = fields.Char(compute="_compute_keys")
    result_storage_key = fields.Char(compute="_compute_keys")

    @api.depends_context(*(context_key for _field, context_key in _CONTEXT_KEYS))
    def _compute_keys(self):
        """Read the keys from the action that opened this dialog.

        The generate action puts each key in the context. The form sends
        that context when it reads the wizard, so the keys are shown once
        and are not written to the transient table.

        """
        values = {
            field: self.env.context.get(context_key) or False
            for field, context_key in _CONTEXT_KEYS
        }
        for wizard in self:
            for field, value in values.items():
                wizard[field] = value
