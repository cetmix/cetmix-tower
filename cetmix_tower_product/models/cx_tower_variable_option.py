# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models


class TowerVariableOption(models.Model):
    _inherit = "cx.tower.variable.option"

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to trigger auto-sync when new options are created"""
        records = super().create(vals_list)

        # Optimization: batch sync triggers instead of calling per-record
        # Aggregate all variables from the created records
        variables = {rec.variable_id for rec in records if rec.variable_id}
        if variables:
            # Batch trigger sync for all affected variables at once
            self._batch_trigger_product_attribute_autosync(variables)

        return records

    def _batch_trigger_product_attribute_autosync(self, variables):
        """Batch trigger auto-sync for multiple variables to avoid N+1 queries"""
        if not variables:
            return

        # Find all product attributes linked to these variables with auto_sync enabled
        attributes = self.env["product.attribute"].search(
            [
                ("tower_variable_id", "in", [var.id for var in variables]),
                ("auto_sync_tower_values", "=", True),
            ]
        )

        # Trigger sync once per attribute (batched approach)
        for attribute in attributes:
            attribute._sync_tower_options()
