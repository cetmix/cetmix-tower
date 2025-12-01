# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class TowerVariableOption(models.Model):
    """
    Model to manage variable options in the Cetmix Tower.

    The model allows defining options
    that are linked to tower variables and can be used to
     manage configurations or settings for those variables.
    """

    _name = "cx.tower.variable.option"
    _description = "Cetmix Tower Variable Options"
    _inherit = ["cx.tower.reference.mixin", "cx.tower.access.mixin"]
    _order = "sequence, name"

    access_level = fields.Selection(
        compute="_compute_access_level",
        readonly=False,
        store=True,
        default=None,
    )
    name = fields.Char(required=True)
    value_char = fields.Char(string="Value", required=True)
    variable_id = fields.Many2one(
        comodel_name="cx.tower.variable",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)

    #  Define SQL constraints to ensure uniqueness of
    # 'value_char' and 'name' per variable
    _sql_constraints = [
        (
            "unique_variable_option",
            "unique (value_char, variable_id)",
            "The combination of Value and Variable must be unique.",
        ),
        (
            "unique_variable_option_name",
            "unique (name, variable_id)",
            "The combination of Name and Variable must be unique.",
        ),
    ]

    @api.depends("variable_id", "variable_id.access_level")
    def _compute_access_level(self):
        """
        Automatically set the access_level based on Variable access level
        """
        for rec in self:
            if rec.variable_id:
                rec.access_level = rec.variable_id.access_level

    @api.constrains("access_level", "variable_id")
    def _check_access_level_consistency(self):
        """
        Ensure that the access level of the variable value is not lower than
        the access level of the associated variable.
        """
        access_level_dict = dict(
            self.fields_get(["access_level"])["access_level"]["selection"]
        )
        for rec in self:
            if not rec.variable_id:
                continue
            if not rec.access_level:
                raise ValidationError(
                    _(
                        "Access level is not defined for '%(option)s'",
                        option=rec.name,
                    )
                )
            if rec.access_level < rec.variable_id.access_level:
                raise ValidationError(
                    _(
                        "The access level for Variable Option '%(value)s' "
                        "cannot be lower than the access level of its "
                        "Variable '%(variable)s'.\n"
                        "Variable Access Level: %(var_level)s\n"
                        "Variable Option Access Level: %(val_level)s",
                        value=rec.name,
                        variable=rec.variable_id.name,
                        var_level=access_level_dict[rec.variable_id.access_level],
                        val_level=access_level_dict[rec.access_level],
                    )
                )

    # Workaround for the default value not being set
    @api.model_create_multi
    def create(self, vals_list):
        variable_obj = self.env["cx.tower.variable"]
        for vals in vals_list:
            # Set access level from the variable
            # if not provided explicitly
            access_level = vals.get("access_level")
            if access_level:
                continue
            variable_id = vals.get("variable_id")
            if variable_id:
                variable = variable_obj.browse(variable_id)
                vals["access_level"] = variable.access_level
        return super().create(vals_list)

    def _get_pre_populated_model_data(self):
        """
        Define the model relationships for reference generation.
        """
        res = super()._get_pre_populated_model_data()
        res.update({"cx.tower.variable.option": ["cx.tower.variable", "variable_id"]})
        return res
