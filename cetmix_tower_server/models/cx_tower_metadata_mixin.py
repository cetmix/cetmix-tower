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
        groups="cetmix_tower_server.group_manager",
    )
    metadata_text = fields.Text(
        help="Additional metadata for this record",
        compute="_compute_metadata_text",
        groups="cetmix_tower_server.group_manager",
    )

    @api.depends("metadata")
    def _compute_metadata_text(self):
        """
        Compute the metadata text for the record
        """
        for record in self:
            record.metadata_text = str(record.metadata) if record.metadata else False

    def update_metadata(self, metadata):
        """
        Updates the metadata for the record.
        Preserves the existing metadata.

        Args:
            metadata (dict): The metadata to update the record with

        Returns:
            bool: True if the metadata was updated, False otherwise
        """
        self.ensure_one()
        # Preserve the existing data in self.metadata.
        self.write({"metadata": {**(self.metadata or {}), **metadata}})
        return True
