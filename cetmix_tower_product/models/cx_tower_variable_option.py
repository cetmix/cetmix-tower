# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models


class TowerVariableOption(models.Model):
    _inherit = "cx.tower.variable.option"

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to trigger auto-sync when new options are created"""
        records = super().create(vals_list)
        for record in records:
            record._trigger_product_attribute_autosync()
        return records

    # No need to override `unlink`: when a Tower option is deleted PostgreSQL
    # cascades the removal of related `product.attribute.value` thanks to the
    # `ondelete="cascade"` on `tower_option_id`.

    def _trigger_product_attribute_autosync(self):
        """Trigger auto-sync for product attributes linked to this option's variable"""
        for record in self:
            if record.variable_id:
                # Find all product attributes linked to this variable
                # with auto_sync enabled
                attributes = self.env["product.attribute"].search(
                    [
                        ("tower_variable_id", "=", record.variable_id.id),
                        ("auto_sync_tower_values", "=", True),
                    ]
                )

                # Trigger sync for each attribute
                for attribute in attributes:
                    attribute._sync_tower_options()
