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

    auto_sync_tower_values = fields.Boolean(
        string="Auto sync values from related Cetmix Tower variable",
        help=(
            "If enabled, attribute values will be automatically synced when "
            "options are added or removed in the linked Tower variable."
        ),
    )

    def action_sync_tower_values(self):
        """Manually sync attribute values from Tower variable"""
        self.ensure_one()
        if not self.tower_variable_id:
            raise ValidationError(_("No Tower Variable selected to sync from."))
        return self._sync_tower_options()

    def _sync_tower_options(self):
        """Sync from Tower variable options - for option-type variables"""
        created_values = self.env["product.attribute.value"]

        # Get all current attribute values for this attribute
        remaining_attribute_values = self.env["product.attribute.value"].search(
            [("attribute_id", "=", self.id)]
        )

        # Get all current Tower options for this variable
        current_tower_options = self.tower_variable_id.option_ids

        existing_names = set(remaining_attribute_values.mapped("name"))
        existing_tower_option_ids = set(
            remaining_attribute_values.mapped("tower_option_id").ids
        )

        # Add new attribute values for new Tower options
        vals_list = []
        for option in current_tower_options:
            # Only create if doesn't exist by tower ID and by name
            if (
                option.id not in existing_tower_option_ids
                and option.value_char not in existing_names
            ):
                vals_list.append(
                    {
                        "name": option.name,
                        "attribute_id": self.id,
                        "tower_option_id": option.id,
                        "tower_variable_reference": self.tower_variable_id.reference,
                    }
                )
                # Add to sets to prevent creating duplicates from this sync batch
                existing_names.add(option.name)
                existing_tower_option_ids.add(option.id)

        if vals_list:
            created_values = self.env["product.attribute.value"].create(vals_list)

        return {
            "created": created_values,
        }
