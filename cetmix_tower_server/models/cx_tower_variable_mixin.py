from odoo import api, fields, models


class TowerValueMixin(models.AbstractModel):
    """Used to implement variables and variable values.
    Inherit in your model if you want to use variables in it.
    """

    _name = "cx.tower.variable.mixin"
    _description = "Tower Variables mixin"

    variable_value_ids = fields.One2many(
        string="Variable Values",
        comodel_name="cx.tower.variable.value",
        compute="_compute_variable_value_ids",
        inverse="_inverse_variable_value_ids",
        help="Variable values for selected record",
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

    @api.model_create_multi
    def create(self, vals_list):
        # Force field recompute on creation
        res = super().create(vals_list)
        res.invalidate_cache(fnames=["variable_value_ids"], ids=res.ids)
        return res

    def unlink(self):
        # Unlink variable values that belong to deleted records
        variable_value_ids = self.variable_value_ids
        super().unlink()
        variable_value_ids.sudo().unlink()

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
            global_values = self.get_global_variable_values(variable_names)

            # In onchange some computed fields of the related models
            #  may be not initialized yet.
            # For this we get data directly
            values = self.env["cx.tower.variable.value"].search(
                [
                    ("model", "=", self._name),
                    ("res_id", "in", self.ids),
                    ("variable_name", "in", variable_names),
                ]
            )
            if values:
                for rec in self:
                    res_vars = global_values.get(
                        rec.id, {}
                    )  # set global values as defaults
                    for variable_name in variable_names:
                        value = values.filtered(
                            lambda v: v.res_id
                            == rec.ids[0]  # id might be not be valid in onchange
                            and v.variable_name == variable_name
                        )
                        if value:
                            res_vars.update({variable_name: value.value_char})

                    res.update({rec.id: res_vars})
            else:
                res = global_values
        # Render templates in values
        for key in res:
            self._render_variable_values(res[key])
        return res

    def get_global_variable_values(self, variable_names):
        """Get global values for variables.
            Such values do not belong to any record.

        This function is used by get_variable_values()
        to compute fallback values.

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
            ("model", "=", False),
            ("variable_name", "in", variable_names),
        ]
        return domain

    def _render_variable_values(self, variables):
        """Renders variable values using other variable values.
        For example we have the following values:
            "server_root": "/opt/server"
            "server_assets": "{{ server_root }}/assets"

        This function will render the "server_assets" variable:
            "server_assets": "/opt/server/assets"

        Args:
            variables (dict): values to complete
        """
        self.ensure_one()
        TemplateMixin = self.env["cx.tower.template.mixin"]
        for key in variables:
            var_value = variables[key]
            # Render only if template is found
            if var_value and "{{ " in var_value:

                # Get variables used in value
                value_vars = TemplateMixin.get_variables_from_code(var_value)

                # Render variables used in value
                res = self.get_variable_values(value_vars)

                # Render value using variables
                variables[key] = TemplateMixin.render_code_custom(
                    var_value, **res[self.id]
                )
