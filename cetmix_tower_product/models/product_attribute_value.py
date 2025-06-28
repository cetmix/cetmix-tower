# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProductAttributeValue(models.Model):
    _inherit = "product.attribute.value"

    # Link to Tower Variable (for reference)
    tower_variable_reference = fields.Char(
        help="Reference to the Tower variable",
        readonly=True,
        index=True,
    )

    # Link to specific Tower records
    tower_option_id = fields.Many2one(
        comodel_name="cx.tower.variable.option",
        ondelete="cascade",
        help="Tower variable option this attribute value represents",
        readonly=True,
    )

    # Computed fields for easy access
    tower_variable_id = fields.Many2one(
        comodel_name="cx.tower.variable",
        compute="_compute_tower_variable_id",
        store=True,
        help="Tower variable associated with this attribute value",
    )

    is_from_tower = fields.Boolean(
        compute="_compute_is_from_tower",
        store=True,
        readonly=True,
        help="True if this attribute value comes from Tower variables",
    )

    @api.depends("tower_option_id")
    def _compute_tower_variable_id(self):
        """Compute the Tower variable ID from either option or value"""
        for record in self:
            if record.tower_option_id:
                record.tower_variable_id = record.tower_option_id.variable_id
            else:
                record.tower_variable_id = False

    @api.depends("tower_option_id")
    def _compute_is_from_tower(self):
        """Check if this attribute value comes from Tower"""
        for record in self:
            record.is_from_tower = bool(record.tower_option_id)

    def get_tower_actual_value(self):
        """Get the actual Tower value for this attribute value"""
        self.ensure_one()

        if self.tower_option_id:
            return self.tower_option_id.value_char

        return self.name

    @api.model_create_multi
    def create(self, vals_list):
        """Prevent manual creation of values for attributes linked to Tower."""

        attribute_ids = {v["attribute_id"] for v in vals_list if "attribute_id" in v}
        if attribute_ids:
            attributes = self.env["product.attribute"].browse(attribute_ids)
            # Create a lookup dict for faster access
            tower_linked_attrs = {
                attr.id: attr.tower_variable_id
                for attr in attributes
                if attr.tower_variable_id
            }
        else:
            tower_linked_attrs = {}

        for vals in vals_list:
            if vals.get("tower_option_id"):
                continue

            attribute_id = vals.get("attribute_id")
            if not attribute_id:
                continue

            if attribute_id in tower_linked_attrs:
                raise UserError(
                    _(
                        "Cannot create attribute values for Tower-linked attributes. "
                        "Please add the option '%(option_name)s' in Cetmix Tower "
                        "instead.",
                        option_name=vals.get("name", "Unknown"),
                    )
                )

        return super().create(vals_list)

    def unlink(self):
        """Prevent manual deletion of values originating from Tower."""

        for record in self:
            if record.tower_option_id or record.attribute_id.tower_variable_id:
                raise UserError(
                    _(
                        "Cannot delete attribute value '%(value_name)s' that is "
                        "synchronised with Cetmix Tower. Remove the corresponding "
                        "option in Cetmix Tower to delete it here.",
                        value_name=record.name,
                    )
                )

        return super().unlink()
