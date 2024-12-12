# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import fields, models


class TowerVariableOption(models.Model):
    _name = "cx.tower.variable.option"
    _description = "Cetmix Tower Variable Options"

    name = fields.Char(string="Option Value", required=True)
    variable_id = fields.Many2one(
        comodel_name="cx.tower.variable",
        string="Variable",
        required=True,
        ondelete="cascade",
        default=lambda self: self.env.context.get("default_variable_id"),
        index=True,
    )

    _sql_constraints = [
        (
            "unique_variable_option",
            "unique (name, variable_id)",
            "Option values must be unique for a variable!",
        )
    ]
