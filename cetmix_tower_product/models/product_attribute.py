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

        # Build domain for variable values - get all values for this variable
        domain = [("variable_id", "=", self.tower_variable_id.id)]

        variable_values = self.env["cx.tower.variable.value"].search(domain)

        for var_value in variable_values:
            value_name = var_value.value_char or var_value.variable_reference

            # Check if already exists by tower_variable_value_id
            existing_by_tower_id = self.env["product.attribute.value"].search(
                [
                    ("attribute_id", "=", self.id),
                    ("tower_variable_value_id", "=", var_value.id),
                ]
            )

            # Check if already exists by name (to prevent duplicate names)
            existing_by_name = self.env["product.attribute.value"].search(
                [("attribute_id", "=", self.id), ("name", "=", value_name)]
            )

            # Only create if doesn't exist by tower ID and by name
            if not existing_by_tower_id and not existing_by_name:
                created_values |= self.env["product.attribute.value"].create(
                    {
                        "name": value_name,
                        "attribute_id": self.id,
                        "tower_variable_value_id": var_value.id,
                        "tower_variable_reference": self.tower_variable_id.reference,
                    }
                )

        return created_values

    def _sync_tower_options(self):
        """Sync from Tower variable options - for option-type variables"""
        created_values = self.env["product.attribute.value"]

        # Get all options for this Tower variable
        tower_options = self.tower_variable_id.option_ids

        for option in tower_options:
            # Check if already exists by tower_option_id
            existing_by_tower_id = self.env["product.attribute.value"].search(
                [("attribute_id", "=", self.id), ("tower_option_id", "=", option.id)]
            )

            # Check if already exists by name (to prevent duplicate names)
            existing_by_name = self.env["product.attribute.value"].search(
                [("attribute_id", "=", self.id), ("name", "=", option.value_char)]
            )

            # Only create if doesn't exist by tower ID and by name
            if not existing_by_tower_id and not existing_by_name:
                created_values |= self.env["product.attribute.value"].create(
                    {
                        "name": option.value_char,
                        "attribute_id": self.id,
                        "tower_option_id": option.id,
                        "tower_variable_reference": self.tower_variable_id.reference,
                    }
                )

        return created_values
