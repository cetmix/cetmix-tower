# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, fields, models
from odoo.exceptions import ValidationError


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

    def get_variable_value(self, variable_reference, no_fallback=False, tower_env=None):
        """Get the value of a variable.
        IMPORTANT: This is the generic method that returns the value of the variable
        for the current record.
        It doesn't evaluate fallback values,eg "jet->template->server->global".
        Inherit and override this method to implement a proper value parsing logic.

        Args:
            variable_reference (str): The reference of the variable to get the value for
            no_fallback (bool): If True, return current record value
                without checking fallback values.
            tower_env (str): Reference of the tower environment, eg 'prod'.
                Returns the value tagged with this environment, or the value
                without environments if there is no such value.
                Without it only the value without environments is returned.
                Has no effect on records whose values can't have environments.
        Returns:
            str: The value of the variable for the current record or None
        """
        self.ensure_one()
        tower_environment = self._get_tower_environment(tower_env)

        # Get the variable value for the current record
        variable_value = self._get_own_variable_value(
            variable_reference, tower_environment, untagged_fallback=True
        )
        if variable_value:
            return variable_value.value_char

    def set_variable_value(self, variable_reference, value, tower_env=None):
        """Set the value of a variable.

        Args:
            variable_reference (str): The reference of the variable to set the value for
            value (str): The value to set for the variable
            tower_env (str): Reference of the tower environment, eg 'prod'.
                Writes the value tagged with this environment.
                If there is no such value, a new value tagged with this
                environment is created. The value without environments
                is never written in this case.
                Without it only the value without environments is written.
                Has no effect on records whose values can't have environments.
        """
        self.ensure_one()
        tower_environment = self._get_tower_environment(tower_env)
        if not self._variable_value_environment_allowed():
            tower_environment = tower_environment.browse()

        # Check if the variable value exists and update it
        variable_value = self._get_own_variable_value(
            variable_reference, tower_environment, untagged_fallback=False
        )
        if variable_value:
            # Do nothing if the value is the same
            if variable_value.value_char == value:
                return
            variable_value.value_char = value
            return

        # Get the variable
        variable = self.env["cx.tower.variable"].get_by_reference(variable_reference)
        if not variable:
            raise ValidationError(
                _(
                    "Variable '%(variable_reference)s' not found",
                    variable_reference=variable_reference,
                )
            )

        # Create a new variable value
        value_vals = {"variable_id": variable.id, "value_char": value}
        if tower_environment:
            value_vals["environment_ids"] = [(6, 0, tower_environment.ids)]
        self.write({"variable_value_ids": [(0, 0, value_vals)]})

    def _get_variable_value_with_fallback(
        self, variable_reference, tower_env, **kwargs
    ):
        """Return the value of a variable following the value application order.
        Used by models that override `get_variable_value` with a fallback.

        Args:
            variable_reference (str): The reference of the variable
            tower_env (str): Reference of the tower environment, eg 'prod'
            **kwargs: the record context passed to
                `_get_variable_values_by_references`, eg `server=self`

        Raises:
            ValidationError: if no environment is found for `tower_env`

        Returns:
            str: The value of the variable or None
        """
        tower_environment = self._get_tower_environment(tower_env)
        variable = self.env["cx.tower.variable"].get_by_reference(variable_reference)
        if not variable:
            return None
        values = variable._get_variable_values_by_references(
            variable_references=[variable_reference],
            tower_env=tower_environment,
            **kwargs,
        )
        return values[variable_reference]

    def _variable_value_environment_allowed(self):
        """Return True if variable values of this model can have environments.
        Override in models whose values can be tagged with environments.

        Returns:
            bool: True if environments are allowed
        """
        return False

    def _get_tower_environment(self, tower_env):
        """Resolve a tower environment reference.

        Args:
            tower_env (str): Reference of the tower environment, eg 'prod'

        Raises:
            ValidationError: if no environment is found for the reference

        Returns:
            cx.tower.environment(): The environment.
                Empty recordset if no reference is provided.
        """
        environment_obj = self.env["cx.tower.environment"]
        if not tower_env:
            return environment_obj
        tower_environment = environment_obj.get_by_reference(tower_env)
        if not tower_environment:
            raise ValidationError(
                _(
                    "Environment '%(tower_env)s' not found",
                    tower_env=tower_env,
                )
            )
        return tower_environment

    def _get_own_variable_value(
        self, variable_reference, tower_environment, untagged_fallback
    ):
        """Return the record's own value of a variable.

        Args:
            variable_reference (str): The reference of the variable
            tower_environment (cx.tower.environment()): The tower environment.
                Ignored if values of this model can't have environments.
            untagged_fallback (bool): Return the value without environments
                if there is no value tagged with the tower environment.

        Returns:
            cx.tower.variable.value(): The value or an empty recordset
        """
        self.ensure_one()
        variable_values = self.variable_value_ids.filtered(
            lambda v: v.variable_reference == variable_reference
        )
        if tower_environment and self._variable_value_environment_allowed():
            tagged_value = variable_values.filtered(
                lambda v: tower_environment in v.environment_ids
            )[:1]
            if tagged_value or not untagged_fallback:
                return tagged_value
        return variable_values.filtered(lambda v: not v.environment_ids)[:1]
