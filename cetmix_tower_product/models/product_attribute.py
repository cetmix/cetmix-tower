# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models
from odoo.exceptions import ValidationError


class ProductAttribute(models.Model):
    _inherit = "product.attribute"

    # Link directly to the Tower Variable
    tower_variable_id = fields.Many2one(
        comodel_name="cx.tower.variable",
        help="Tower variable that will be used as source for attribute values. "
        "Both predefined options and actual values will be available.",
    )

    def action_sync_tower_values(self):
        """Manually sync attribute values from Tower variable"""
        self.ensure_one()
        if not self.tower_variable_id:
            raise ValidationError(_("No Tower Variable selected to sync from."))

        return self._sync_tower_values()

    def _sync_tower_values(self):
        """Core sync logic for Tower values"""
        self.ensure_one()
        created_values = self.env["product.attribute.value"]

        # Check variable type and sync accordingly
        if self.tower_variable_id.variable_type == "o":
            # For option-type variables, sync from Tower variable options
            created_values |= self._sync_tower_options()
        else:
            # For other variable types (e.g., 's'), sync from Tower variable values
            created_values |= self._sync_tower_variable_values()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sync Complete"),
                "message": _("%d attribute values synchronized from Tower variable.")
                % len(created_values),
                "type": "success",
            },
        }

    def _sync_tower_variable_values(self):
        """Sync from Tower variable values - get all values"""
        created_values = self.env["product.attribute.value"]
        all_attribute_values = self.env["product.attribute.value"].search(
            [("attribute_id", "=", self.id)]
        )
        existing_names = set(all_attribute_values.mapped("name"))
        existing_tower_value_ids = set(
            all_attribute_values.mapped("tower_variable_value_id").ids
        )

        # Build domain for variable values - get all values for this variable
        domain = [("variable_id", "=", self.tower_variable_id.id)]

        variable_values = self.env["cx.tower.variable.value"].search(domain)
        vals_list = []
        for var_value in variable_values:
            value_name = var_value.value_char or var_value.variable_reference

            # Only create if doesn't exist by tower ID and by name
            if (
                var_value.id not in existing_tower_value_ids
                and value_name not in existing_names
            ):
                vals_list.append(
                    {
                        "name": value_name,
                        "attribute_id": self.id,
                        "tower_variable_value_id": var_value.id,
                        "tower_variable_reference": self.tower_variable_id.reference,
                    }
                )
                # Add to sets to prevent creating duplicates from this sync batch
                existing_names.add(value_name)
                existing_tower_value_ids.add(var_value.id)

        if vals_list:
            created_values |= self.env["product.attribute.value"].create(vals_list)

        return created_values

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
