# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CxTowerDronePayloadKeyWizard(models.TransientModel):
    """Show a freshly generated payload key so it can be copied."""

    _name = "cx.tower.drone.payload.key.wizard"
    _description = "Show Generated Payload Key"

    controller_id = fields.Many2one(
        comodel_name="cx.tower.drone.controller",
        required=True,
        ondelete="cascade",
    )
    payload_key = fields.Char(readonly=True, store=False)
