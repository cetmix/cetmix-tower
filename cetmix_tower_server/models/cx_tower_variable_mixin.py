# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, fields, models
from odoo.exceptions import ValidationError


class TowerVariableMixin(models.AbstractModel):
    """Used to implement variables and variable values.
    Inherit in your model if you want to use variables in it.
    """

    _name = "cx.tower.variable.mixin"
    _description = "Tower Variables mixin"

    variable_value_ids = fields.One2many(
        string="Variable Values",
        comodel_name="cx.tower.variable.value",
        auto_join=True,
        help="Variable values for selected record",
    )

    def set_variable_value(self, variable_reference, value):
        """Set the value of a variable.

        Args:
            variable_reference (str): The reference of the variable to set the value for
            value (str): The value to set for the variable
        """
        self.ensure_one()

        # Check if the variable value exists and update it
        variable_value = self.variable_value_ids.filtered(
            lambda v: v.variable_reference == variable_reference
        )
        if variable_value:
            variable_value.value_char = value
            return

        # Get the variable
        variable = self.env["cx.tower.variable"].get_by_reference(variable_reference)
        if not variable:
            raise ValidationError(
                _(
                    "Variable '%(variable_reference)s' not found",
                    variable_reference=variable_reference,
                )
            )

        # Create a new variable value
        variable_value = self.write(
            {
                "variable_value_ids": [
                    (0, 0, {"variable_id": variable.id, "value_char": value})
                ]
            }
        )
