from odoo import fields, models


class TowerVariable(models.Model):
    _name = "cx.tower.variable"
    _description = "Cetmix Tower Variable"

    name = fields.Char(string="Name", required=True)


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

            # Ensure variables are list
            if not isinstance(variables, list):
                variables = list(variables)

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
