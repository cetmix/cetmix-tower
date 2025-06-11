# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import logging

from odoo import fields, models
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class TowerVariableMixin(models.AbstractModel):
    """Used to implement variables and variable values.
    Inherit in your model if you want to use variables in it.
    """

    _name = "cx.tower.variable.mixin"
    _description = "Tower Variables mixin"

    SYSTEM_VARIABLE_REFERENCE = "tower"

    variable_value_ids = fields.One2many(
        string="Variable Values",
        comodel_name="cx.tower.variable.value",
        auto_join=True,
        help="Variable values for selected record",
    )

    def get_variable_values(
        self, variable_references, apply_modifiers=True, system_variable_values=None
    ):
        """Get variable values for selected records

        Args:
            variable_references (list of Char): variable names
            apply_modifiers (bool): apply Python modifiers to the values
            system_variable_values (dict): values for the `tower` system variable

        Returns:
            dict {record_id: {variable_reference: value}}
        """
        res = {}

        # Get global values first
        if variable_references:
            global_values = self.get_global_variable_values(variable_references)

            # Compute variable values for each record
            for rec in self:
                # 1. System variable values
                res_vars = {"tower": system_variable_values or {}}

                # 2. Global values
                res_vars.update(global_values.get(rec.id, {}))

                # 3. Record values
                for variable_reference in variable_references:
                    # System variable values are already handled above
                    if variable_reference == self.SYSTEM_VARIABLE_REFERENCE:
                        continue
                    value = rec.variable_value_ids.filtered(
                        lambda v,
                        variable_reference=variable_reference: v.variable_reference
                        == variable_reference
                    )
                    if value:
                        res_vars.update({variable_reference: value.value_char})

                res.update({rec.id: res_vars})

            # Final render
            # Render templates in values
            for variable_values in res.values():
                self._render_variable_values(
                    variable_values, system_variable_values=system_variable_values
                )

        # Apply modifiers
        if apply_modifiers:
            self._apply_modifiers(res)
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
                    # System variable values are already handled above
                    if variable_reference == self.SYSTEM_VARIABLE_REFERENCE:
                        continue
                    # Get variable value
                    value = values.filtered(
                        lambda v,
                        variable_reference=variable_reference: v.variable_reference
                        == variable_reference
                    )
                    res_vars.update(
                        {variable_reference: value.value_char if value else None}
                    )
                res.update({rec.id: res_vars})
        return res

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

    def _render_variable_values(self, variable_values, system_variable_values=None):
        """Renders variable values using other variable values.
        For example we have the following values:
            "server_root": "/opt/server"
            "server_assets": "{{ server_root }}/assets"

        This function will render the "server_assets" variable:
            "server_assets": "/opt/server/assets"

        Args:
            variable_values (dict): values to complete
            system_variable_values (dict): values for the `tower` system variable
        """
        self.ensure_one()
        TemplateMixin = self.env["cx.tower.template.mixin"]
        for key, var_value in variable_values.items():
            # Render only if template is found
            if var_value and "{{ " in var_value:
                # Get variables used in value
                value_vars = TemplateMixin.get_variables_from_code(var_value)

                # Render variables used in value
                res = self.get_variable_values(
                    value_vars,
                    apply_modifiers=True,
                    system_variable_values=system_variable_values,
                )

                # Render value using variables
                variable_values[key] = TemplateMixin.render_code_custom(
                    var_value, **res[self.id]
                )

    def _apply_modifiers(self, variable_values):
        """Apply pre-defined Python expression to the dictionary
            of variable values.

        Args:
            variable_values (dict): variable values
            {record_id: {variable_reference: value}}
        """
        variable_obj = self.env["cx.tower.variable"]

        for record_id, values in variable_values.items():
            for variable_reference, value in values.items():
                if not value:
                    continue

                # ORM should cache resolved variables
                variable = variable_obj.get_by_reference(variable_reference)

                # Should never happen.. anyway
                if not variable:
                    continue

                # Skip if no expression to apply
                if not variable.applied_expression:
                    continue

                # Evaluate expression
                eval_context = variable_obj._get_eval_context(value)
                try:
                    safe_eval(
                        variable.applied_expression,
                        eval_context,
                        mode="exec",
                        nocopy=True,
                    )
                    variable_values[record_id][variable_reference] = eval_context.get(
                        "result"
                    )
                except Exception as e:
                    _logger.error(
                        "Error evaluating applied expression for "
                        "variable %s value %s: %s",
                        variable.name,
                        value,
                        str(e),
                    )
