# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CxTowerEnvironment(models.Model):
    """Environment, e.g. Production or Development.

    Variable values tagged with an environment are used only
    for Jets in that environment.
    """

    _name = "cx.tower.environment"
    _inherit = [
        "cx.tower.reference.mixin",
    ]
    _description = "Cetmix Tower Environment"
    _order = "name"

    color = fields.Integer(help="For better visualization in views")

    @api.ondelete(at_uninstall=False)
    def _unlink_except_used_in_variable_values(self):
        """Do not delete environments used in variable values.

        Removing the environment from a value would silently turn
        an environment-specific value into a value for all environments.
        """
        used_values = (
            self.env["cx.tower.variable.value"]
            .sudo()
            .with_context(active_test=False)
            .search([("environment_ids", "in", self.ids)])
        )
        if used_values:
            raise ValidationError(
                _(
                    "Cannot delete environment(s) %(environments)s:"
                    " they are used in variable values %(values)s.",
                    environments=", ".join(
                        used_values.environment_ids.filtered(
                            lambda environment: environment in self
                        ).mapped("name")
                    ),
                    values=", ".join(used_values.mapped("reference")),
                )
            )
