# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models


class TowerVariable(models.Model):
    _name = "cx.tower.variable"
    _description = "Cetmix Tower Variable"
    _inherit = ["cx.tower.reference.mixin"]

    _order = "name"

    value_ids = fields.One2many(
        string="Values",
        comodel_name="cx.tower.variable.value",
        inverse_name="variable_id",
    )
    value_ids_count = fields.Integer(
        string="Value Count", compute="_compute_value_ids_count", store=True
    )
    note = fields.Text()

    _sql_constraints = [("name_uniq", "unique (name)", "Variable names must be unique")]

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
