# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


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

    def action_open_tower_record(self):
        """Open the related Tower record"""
        self.ensure_one()

        if self.tower_option_id:
            return {
                "type": "ir.actions.act_window",
                "name": "Tower Variable Option",
                "res_model": "cx.tower.variable.option",
                "res_id": self.tower_option_id.id,
                "view_mode": "form",
                "target": "current",
            }

        # No linked Tower record for string values anymore
