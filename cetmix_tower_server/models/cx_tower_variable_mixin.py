# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import uuid

from odoo import fields, models


class TowerVariableMixin(models.AbstractModel):
    """Used to implement variables and variable values.
    Inherit in your model if you want to use variables in it.
    """

    _name = "cx.tower.variable.mixin"
    _description = "Tower Variables mixin"

    variable_value_ids = fields.One2many(
        string="Variable Values",
        comodel_name="cx.tower.variable.value",
        auto_join=True,
        help="Variable values for selected record",
    )

    def get_variable_values(self, variable_references):
        """Get variable values for selected records

        Args:
            variable_references (list of Char): variable names

        Returns:
            dict {record_id: {variable_reference: value}}
        """
        res = {}

        # Get global values first
        if variable_references:
            global_values = self.get_global_variable_values(variable_references)

            # Get record wise values
            for rec in self:
                res_vars = global_values.get(
                    rec.id, {}
                )  # set global values as defaults
                for variable_reference in variable_references:
                    # Check if this is a system variable
                    system_value = self._get_system_variable_value(variable_reference)
                    if system_value:
                        res_vars.update({variable_reference: system_value})

                    # Get regular value
                    else:
                        value = rec.variable_value_ids.filtered(
                            lambda v,
                            variable_reference=variable_reference: v.variable_reference
                            == variable_reference
                        )
                        if value:
                            res_vars.update({variable_reference: value.value_char})

                res.update({rec.id: res_vars})

            # Render templates in values
            for variables in res.values():
                self._render_variable_values(variables)

        return res

    def get_global_variable_values(self, variable_references):
        """Get global values for variables.
            Such values do not belong to any record.

        This function is used by get_variable_values()
        to compute fallback values.

        Args:
            variable_references (list of Char): variable names

        Returns:
            dict {record_id: {variable_reference: value}}
        """
        res = {}

        if variable_references:
            values = self.env["cx.tower.variable.value"].search(
                self._compose_variable_global_values_domain(variable_references)
            )
            for rec in self:
                res_vars = {}
                for variable_reference in variable_references:
                    # Get variable value
                    value = values.filtered(
                        lambda v,
                        variable_reference=variable_reference: v.variable_reference
                        == variable_reference
                    )
                    res_vars.update({variable_reference: value.value_char or None})
                res.update({rec.id: res_vars})
        return res

    def _get_current_server(self):
        """Get current server record.
            This is needed to render system variables properly.

        Returns:
            cx.tower.server(): server record
        """
        self.ensure_one()

        if self._name == "cx.tower.server":
            server = self
        elif self._name == "cx.tower.variable.value" and self.server_id:
            server = self.server_id
        else:
            server = None
        return server

    def _get_system_variable_value(self, variable_reference):
        """Get the value of a system variable. Eg `tower.server.partner_name`

        Args:
            variable_reference (Char): variable value

        Returns:
            dict(): populates `tower` variable with with values.
                {
                    'server': {..server vals..},
                    'tools': {..helper tools vals...}
                }.
        """

        # This works for a single record only!
        self.ensure_one()

        variable_value = {}
        if variable_reference == "tower":
            variable_value.update(
                {
                    "server": self._parse_system_variable_server(),
                    "tools": self._parse_system_variable_tools(),
                }
            )

        return variable_value

    def _parse_system_variable_server(self):
        """Parser system variable of `server` type.

        Returns:
            dict(): `server` values of the `tower` variable.
        """
        # Get current server
        values = {}
        server = self._get_current_server()
        if server:
            values = {
                "name": server.name,
                "reference": server.reference,
                "username": server.ssh_username,
                "partner_name": server.partner_id.name if server.partner_id else False,
                "ipv4": server.ip_v4_address,
                "ipv6": server.ip_v6_address,
                "status": server.status,
            }
        return values

    def _parse_system_variable_tools(self):
        """Parser system variable of `tools` type.

        Returns:
            dict(): `server` values of the `tower` variable.
        """
        values = {
            "uuid": uuid.uuid4(),
            "today": str(fields.Date.today()),
            "now": str(fields.Datetime.now()),
        }
        return values

    def _compose_variable_global_values_domain(self, variable_references):
        """Compose domain for global variables
        Args:
            variable_references (list of Char): variable names

        Returns:
            domain
        """
        domain = [
            ("is_global", "=", True),
            ("variable_reference", "in", variable_references),
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
