from odoo import fields, models


class TowerValueMixin(models.AbstractModel):
    _name = "cx.tower.variable.mixin"
    _description = "Tower Variables mixin"

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

    def get_variable_values(self, variable_names):
        """Get variable values for selected records

        Args:
            variable_names (list of Char): variable names

        Returns:
            dict {record_id: {variable_name: value}}
        """
        res = {}

        if variable_names:
            # Get fallback values
            self.get_global_variable_values(variable_names)

            # In onchange some computed fields of the related models
            #  may be not initialized yet.
            # For this we get data directly from db
            values = self.env["cx.tower.variable.value"].search(
                [
                    ("model", "=", self._name),
                    ("res_id", "in", self.ids),
                    ("variable_name", "in", variable_names),
                ]
            )
            if values:
                for rec in self:
                    res_vars = {}
                    for variable_name in variable_names:
                        value = values.filtered(
                            lambda v: v.res_id == rec.ids[0]
                            and v.variable_name == variable_name
                        )
                        res_vars.update({variable_name: value.value_char or None})
                    res.update({rec.id: res_vars})
            else:
                res = {
                    rec.id: {variable_name: None for variable_name in variable_names}
                    for rec in self
                }
        return res

    def get_global_variable_values(self, variable_names):
        """Get global values for variables
        Override this function to implement own flow

        Args:
            variable_names (list of Char): variable names

        Returns:
            dict {record_id: {variable_name: value}}
        """
        res = {}

        if variable_names:
            values = self.env["cx.tower.variable.value"].search(
                self._compose_variable_global_values_domain(variable_names)
            )
            for rec in self:
                res_vars = {}
                for variable_name in variable_names:
                    value = values.filtered(lambda v: v.variable_name == variable_name)
                    res_vars.update({variable_name: value.value_char or None})
                res.update({rec.id: res_vars})
        return res

    def _compose_variable_global_values_domain(self, variable_names):
        """Compose domain for global variables
        Args:
            variable_names (list of Char): variable names

        Returns:
            domain
        """
        domain = [
            ("variable_name", "in", variable_names),
        ]
        return domain
