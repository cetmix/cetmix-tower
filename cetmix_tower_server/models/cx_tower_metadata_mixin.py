# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class CxTowerMetadataMixin(models.AbstractModel):
    """Used to implement metadata in models."""

    _name = "cx.tower.metadata.mixin"
    _description = "Cetmix Tower metadata mixin"

    metadata = fields.Json(
        help="Additional metadata for this record",
        readonly=True,
    )
    metadata_text = fields.Text(
        help="Additional metadata for this record",
        compute="_compute_metadata_text",
    )

    @api.depends("metadata")
    def _compute_metadata_text(self):
        """
        Compute the metadata text for the record
        """
        for record in self:
            record.metadata_text = str(record.metadata) if record.metadata else False
