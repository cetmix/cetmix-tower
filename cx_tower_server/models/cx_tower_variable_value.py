from odoo import fields, models


class TowerVariableValue(models.Model):
    _name = "cx.tower.variable.value"
    _description = "Cetmix Tower Variable"
    _rec_name = "variable_name"
    _order = "variable_name"

    variable_id = fields.Many2one(string="Variable", comodel_name="cx.tower.variable")
    variable_name = fields.Char(related="variable_id.name", store=True, index=True)
    model = fields.Char(string="Related Model", index=True)
    res_id = fields.Integer(string="Record ID")
    value_char = fields.Char(string="Value", required=True)

    _sql_constraints = [
        (
            "tower_variable_value_uniq",
            "unique (variable_id,model,res_id)",
            "Variable can be declared only once for the same record!",
        )
    ]
