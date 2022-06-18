from odoo import _, api, fields, models


class TowerVariable(models.Model):
    _name = "cx.tower.variable"
    _description = "Cetmix Tower Variable"
    _order = "name"

    name = fields.Char(string="Name", required=True)
    value_ids = fields.One2many(
        string="Values",
        comodel_name="cx.tower.variable.value",
        inverse_name="variable_id",
    )
    value_ids_count = fields.Integer(
        string="Values", compute="_compute_value_ids_count", store=True
    )

    @api.depends("value_ids", "value_ids.variable_id")
    def _compute_value_ids_count(self):
        """Count number of values for the variable"""
        for rec in self:
            rec.value_ids_count = len(rec.value_ids)

    def action_open_values(self):
        context = self.env.context.copy()
        context.update(
            {
                "default_variable_id": self.id,
            }
        )

        return {
            "type": "ir.actions.act_window",
            "name": _("Variable Values"),
            "res_model": "cx.tower.variable.value",
            "views": [[False, "tree"]],
            "target": "current",
            "context": context,
            "domain": [("variable_id", "=", self.id)],
        }
