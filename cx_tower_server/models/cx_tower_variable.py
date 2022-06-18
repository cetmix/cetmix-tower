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
            if not rec.model:
                rec.is_global = True
            else:
                rec.is_global = False

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
            self.update({"model": self.record_ref._name, "res_id": self.record_ref.id})


class TowerValueMixin(models.AbstractModel):
    _name = "cx.tower.variable.mixin"

    variable_value_ids = fields.One2many(
        string="Variable Values",
        comodel_name="cx.tower.variable.value",
        compute="_compute_variable_value_ids",
        inverse="_inverse_variable_value_ids",
    )

    def _compute_variable_value_ids(self):
        """Compute variable values"""
        # Pre-fetch all values to avoid multiple queries
        values = self.env["cx.tower.variable.value"].search(
            [("model", "=", self._name), ("res_id", "in", self.ids)]
        )
        for rec in self:
            rec.variable_value_ids = values.filtered(lambda v: v.res_id == rec.id)

    def _inverse_variable_value_ids(self):
        """Store variable values for selected record"""
        current_values = self.env["cx.tower.variable.value"].search(
            [
                ("model", "=", self._name),
                ("res_id", "in", self.ids),
                ("res_id", "in", self.ids),
            ]
        )
        new_vals = []

        # All values are deleted
        if not self.variable_value_ids and current_values:
            current_values.unlink()
        elif not current_values:
            # Store new values only
            new_vals = [
                {
                    "model": self._name,
                    "res_id": self.id,
                    "variable_id": line.variable_id.id,
                    "value_char": line.value_char,
                }
                for line in self.variable_value_ids
            ]
        else:
            # Store new values
            new_vals = [
                {
                    "model": self._name,
                    "res_id": self.id,
                    "variable_id": line.variable_id.id,
                    "value_char": line.value_char,
                }
                for line in self.variable_value_ids
                if line.id not in current_values.ids
            ]
            vals_to_delete = current_values.filtered(
                lambda v: v.id not in self.variable_value_ids.ids
            )
            if vals_to_delete:
                vals_to_delete.unlink()

        # Create new variable values
        if new_vals:
            self.env["cx.tower.variable.value"].create(new_vals)

    def get_variable_values(self, variables):
        """Get variable values for selected records

        Args:
            variables (list of Char): variable names

        Returns:
            dict {record_id: {variable: value}}
        """
        res = {}

        if len(variables):

            # In onchange some computed fields of the related models
            #  may be not initialized yet.
            # For this we get data directly from db
            values = self.env["cx.tower.variable.value"].search(
                [
                    ("model", "=", self._name),
                    ("res_id", "in", self.ids),
                    ("variable_name", "in", variables),
                ]
            )
            for rec in self:
                res_vars = {}
                for variable in variables:
                    value = values.filtered(
                        lambda v: v.res_id == rec.ids[0] and v.variable_name == variable
                    )
                    res_vars.update({variable: value.value_char if value else None})
                res.update({rec.id: res_vars})
        return res