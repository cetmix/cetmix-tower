# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class CxTowerCustomVariableValueMixin(models.AbstractModel):
    """
    Custom variable values.
    """

    _name = "cx.tower.custom.variable.value.mixin"
    _description = "Custom variable values"

    variable_id = fields.Many2one(
        "cx.tower.variable",
    )
    variable_type = fields.Selection(related="variable_id.variable_type", readonly=True)
    value_char = fields.Char(
        string="Value",
        compute="_compute_value_char",
        readonly=False,
        store=True,
        help="Automatically populated from selected option. "
        "Manual edits will be overwritten when option changes.",
    )
    option_id = fields.Many2one(
        "cx.tower.variable.option", domain="[('variable_id', '=', variable_id)]"
    )

    variable_value_id = fields.Many2one("cx.tower.variable.value")
    required = fields.Boolean(
        related="variable_value_id.required",
        readonly=True,
        store=True,
    )

    @api.depends("option_id", "variable_id", "variable_type")
    def _compute_value_char(self):
        """
        Compute value_char based on selected option for option-type variables.
        For non-option variables, value_char is cleared to allow manual input.
        """
        for rec in self:
            if rec.variable_id and rec.variable_type == "o" and rec.option_id:
                rec.value_char = rec.option_id.value_char
            else:
                rec.value_char = ""

    @api.onchange("variable_id")
    def _onchange_variable_id(self):
        """
        Reset option_id when variable changes.
        """
        self.update({"option_id": None})
