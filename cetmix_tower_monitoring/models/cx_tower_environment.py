# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, models
from odoo.exceptions import ValidationError


class CxTowerEnvironment(models.Model):
    _inherit = "cx.tower.environment"

    @api.ondelete(at_uninstall=False)
    def _unlink_except_used_in_template_metrics(self):
        """Do not delete environments used in Jet Template metrics.

        Removing the environment from a template metric would silently turn
        an environment-specific metric into a metric for all jets.
        """
        used_metrics = (
            self.env["cx.tower.jet.template.metric"]
            .sudo()
            .search([("environment_ids", "in", self.ids)])
        )
        if used_metrics:
            raise ValidationError(
                _(
                    "Cannot delete environment(s) %(environments)s:"
                    " they are used in Jet Template metrics %(metrics)s.",
                    environments=", ".join(
                        used_metrics.environment_ids.filtered(
                            lambda environment: environment in self
                        ).mapped("name")
                    ),
                    metrics=", ".join(used_metrics.mapped("reference")),
                )
            )
