# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ReferencesVariableOption(models.Model):
    _name = "cx.tower.reference.variable.option"
    _inherit = ["cx.tower.reference.mixin"]

    name = fields.Char(related="variable_id.name", required=True)
    reference = fields.Char(related="variable_id.reference", readonly=True)
    option = fields.Char(required=True)
    variable_id = fields.Many2one(
        comodel_name="cx.tower.variable",
        string="Variable",
        required=True,
        ondelete="cascade",
        index=True,
    )
    variable_option_reference = fields.Char(
        string="Variable Option",
        compute="_compute_reference_",
        readonly=False,
        help="Automatically generated reference combining variable and option.",
    )

    @api.depends("variable_id.reference", "option")
    def _compute_reference_(self):
        """
        Compute the 'variable_option_reference' field by concatenating the
        reference of the associated variable with a sanitized version of
        the option value.
        The computed reference follows the format:
        '<variable_reference>_option_<sanitized_option>'.

        Example:
            If variable reference is 'odoo__version' and option is '16.0',
            the result will be 'odoo__version_option_160'.
        """
        for record in self:
            if record.variable_id and record.option:
                variable_ref = record.variable_id.reference or ""
                option_ref = self._generate_or_fix_reference(record.option)
                record.variable_option_reference = f"{variable_ref}_option_{option_ref}"
