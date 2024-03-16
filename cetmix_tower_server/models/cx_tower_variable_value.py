# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class TowerVariableValue(models.Model):
    _name = "cx.tower.variable.value"
    _description = "Cetmix Tower Variable"
    _rec_name = "variable_name"
    _order = "variable_name"

    variable_id = fields.Many2one(string="Variable", comodel_name="cx.tower.variable")
    variable_name = fields.Char(related="variable_id.name", store=True, index=True)
    is_global = fields.Boolean(
        string="Global",
        compute="_compute_is_global",
        inverse="_inverse_is_global",
        store=True,
    )

    value_char = fields.Char(string="Value", required=True)
    note = fields.Text(related="variable_id.note", readonly=True)

    # Direct model relations.
    # Following functions should be updated when a new m2o field is added:
    #   -  `_used_in_models()`
    #   -  `_compute_is_global()`: add you field to 'depends'
    # Define a `unique` constraint for new model too.
    server_id = fields.Many2one(
        comodel_name="cx.tower.server", index=True, ondelete="cascade"
    )

    _sql_constraints = [
        (
            "tower_variable_value_uniq",
            "unique (variable_id,server_id,is_global)",
            "Variable can be declared only once for the same record!",
        )
    ]

    @api.constrains("is_global", "value_char")
    def _constraint_global_unique(self):
        """Ensure that there is only one global value exist for the same variable

        Hint to devs:
            `unique nulls not distinct (variable_id,server_id,global_id)`
            can be used instead in PG 15.0+
        """
        for rec in self:
            if rec.is_global:
                val_count = self.search_count(
                    [("variable_id", "=", rec.variable_id.id), ("is_global", "=", True)]
                )
                if val_count > 1:
                    # NB: there is a value check in tests for this message.
                    # Update `test_variable_value_toggle_global`
                    # if you modify this message in your code.
                    raise ValidationError(
                        _(
                            "Only one global value can be defined"
                            " for variable '%(var)s'",
                            var=rec.variable_id.name,
                        )
                    )

    def _used_in_models(self):
        """Returns information about models which use this mixin.

        Returns:
            dict(): of the following format:
                {"model.name": ("m2o_field_name", "model_description")}
            Eg:
                {"my.custom.model": ("much_model_id", "Much Model")}
        """
        return {"cx.tower.server": ("server_id", "Server")}

    def _check_is_global(self):
        """
        This is a helper function used to define
         which variables are considered 'Global'
        Override it to implement your custom logic.

        Returns:
            bool:  True if global else False
        """

        self.ensure_one()
        is_global = True

        # Get m2o field values for all models that use variables.
        # If none of them is set such value is considered 'global'.
        for related_model_info in self._used_in_models().values():
            m2o_field = related_model_info[0]
            if self[m2o_field]:
                is_global = False
                break
        return is_global

    @api.depends("server_id")
    def _compute_is_global(self):
        """
        If variable considered `global` when it's not linked to any record.
        """
        for rec in self:
            rec.is_global = rec._check_is_global()

    def _inverse_is_global(self):
        """Triggered when `is_global` is updated"""
        global_values = self.filtered("is_global")
        if global_values:
            values_to_set = {}

            # Set m2o fields related to variable using models to 'False'
            for related_model_info in self._used_in_models().values():
                m2o_field = related_model_info[0]
                values_to_set.update({m2o_field: False})
            global_values.write(values_to_set)

        # Check if we are trying to remove 'global' from value
        #  that doesn't belong to any record.
        record_related_values = self - global_values
        for record in record_related_values:
            if record._check_is_global():
                # NB: there is a value check in tests for this message.
                # Update `test_variable_value_toggle_global` if you modify this message.
                raise ValidationError(
                    _(
                        "Cannot change 'global' status for "
                        "'%(var)s' with value '%(val)s'."
                        "\nTry to assigns it to a record instead.",
                        var=record.variable_id.name,
                        val=record.value_char,
                    )
                )
