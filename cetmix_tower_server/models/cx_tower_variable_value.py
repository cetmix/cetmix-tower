from odoo import api, fields, models


class TowerVariableValue(models.Model):
    _name = "cx.tower.variable.value"
    _description = "Cetmix Tower Variable"
    _rec_name = "variable_name"
    _order = "variable_name"

    variable_id = fields.Many2one(string="Variable", comodel_name="cx.tower.variable")
    variable_name = fields.Char(related="variable_id.name", store=True, index=True)
    model = fields.Char(string="Related Model", index=True)
    res_id = fields.Integer(string="Record ID")
    record_ref = fields.Reference(
        string="Record",
        selection="_referable_models",
        compute="_compute_record_ref",
        inverse="_inverse_record_ref",
    )
    is_global = fields.Boolean(
        string="Global", compute="_compute_is_global", inverse="_inverse_is_global"
    )
    value_char = fields.Char(string="Value", required=True)
    note = fields.Text(related="variable_id.note", readonly=True)

    _sql_constraints = [
        (
            "tower_variable_value_uniq",
            "unique (variable_id,model,res_id)",
            "Variable can be declared only once for the same record!",
        )
    ]

    def _compute_is_global(self):
        """If variable is global"""
        for rec in self:
            if rec.model:
                rec.is_global = False
            else:
                rec.is_global = True

    def _inverse_is_global(self):
        if self.is_global:
            self.update({"model": None, "res_id": None})

    @api.model
    def _referable_models(self):
        """Models that can have variable values"""
        return [("cx.tower.server", "Server")]

    @api.depends("model", "res_id")
    def _compute_record_ref(self):
        """Compose record reference"""
        for rec in self:
            if rec.model and rec.res_id:
                res = self.env[rec.model].sudo().search([("id", "=", rec.res_id)])
                if res:
                    rec.record_ref = res
                else:
                    rec.record_ref = None
            else:
                rec.record_ref = None

    def _inverse_record_ref(self):
        """Set model and res id based on reference"""
        if self.record_ref:
            self.write({"model": self.record_ref._name, "res_id": self.record_ref.id})
