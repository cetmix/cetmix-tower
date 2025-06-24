# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models
from odoo.exceptions import ValidationError


class ProductAttribute(models.Model):
    _inherit = "product.attribute"

    # Link directly to the Tower Variable
    tower_variable_id = fields.Many2one(
        comodel_name="cx.tower.variable",
        domain=[("variable_type", "=", "o")],
        help="Tower variable options",
    )

    def action_sync_tower_values(self):
        """Manually sync attribute values from Tower variable"""
        self.ensure_one()
        if not self.tower_variable_id:
            raise ValidationError(_("No Tower Variable selected to sync from."))
        return self._sync_tower_options()

    def _sync_tower_values(self):
        """[REMOVED: Only sync options now]"""
        # This method is no longer needed, kept for backward compatibility if called
        return self._sync_tower_options()

    def _sync_tower_options(self):
        """Sync from Tower variable options - for option-type variables"""
        created_values = self.env["product.attribute.value"]
        all_attribute_values = self.env["product.attribute.value"].search(
            [("attribute_id", "=", self.id)]
        )
        existing_names = set(all_attribute_values.mapped("name"))
        existing_tower_option_ids = set(
            all_attribute_values.mapped("tower_option_id").ids
        )

        # Get all options for this Tower variable
        tower_options = self.tower_variable_id.option_ids
        vals_list = []
        for option in tower_options:
            # Only create if doesn't exist by tower ID and by name
            if (
                option.id not in existing_tower_option_ids
                and option.value_char not in existing_names
            ):
                vals_list.append(
                    {
                        "name": option.value_char,
                        "attribute_id": self.id,
                        "tower_option_id": option.id,
                        "tower_variable_reference": self.tower_variable_id.reference,
                    }
                )
                # Add to sets to prevent creating duplicates from this sync batch
                existing_names.add(option.value_char)
                existing_tower_option_ids.add(option.id)

        if vals_list:
            created_values |= self.env["product.attribute.value"].create(vals_list)

        return created_values
