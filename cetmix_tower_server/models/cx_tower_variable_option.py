# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import fields, models


class TowerVariableOption(models.Model):
    """
    Model to manage variable options in the Cetmix Tower.

    The model allows defining options
    that are linked to tower variables and can be used to
     manage configurations or settings for those variables.

    Attributes:
        name (str): The value of the option (e.g., "17.0").
        variable_id (Many2one): A reference to the 'cx.tower.variable'
        model that associates this option with a particular tower variable.
        sequence (int): A sequence number to control the ordering
        of the options.

    SQL Constraints:
        - Ensures that the combination of `name` and `variable_id`
        is unique across the system.
    """

    _name = "cx.tower.variable.option"
    _description = "Cetmix Tower Variable Options"
    _order = "sequence, name"

    name = fields.Char(string="Option Value", required=True)
    variable_id = fields.Many2one(
        comodel_name="cx.tower.variable",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)

    # Define a SQL constraint to ensure the combination of
    # 'name' and 'variable_id' is unique
    _sql_constraints = [
        (
            "unique_variable_option",
            "unique (name, variable_id)",
            "The combination of Name and Variable must be unique.",
        )
    ]
