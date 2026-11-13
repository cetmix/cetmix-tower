# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CxTowerJetTemplateMetric(models.Model):
    """Metric that jets of a Jet Template get automatically."""

    _name = "cx.tower.jet.template.metric"
    _inherit = ["cx.tower.reference.mixin", "cx.tower.yaml.mixin"]
    _description = "Cetmix Tower Jet Template Metric"
    _order = "jet_template_id, id"

    name = fields.Char(related="metric_id.name", readonly=True)
    jet_template_id = fields.Many2one(
        comodel_name="cx.tower.jet.template",
        required=True,
        index=True,
        ondelete="cascade",
    )
    metric_id = fields.Many2one(
        comodel_name="cx.tower.metric",
        required=True,
        index=True,
        ondelete="cascade",
        yaml_export="reference",
    )
    environment_ids = fields.Many2many(
        comodel_name="cx.tower.environment",
        relation="cx_tower_jet_template_metric_environment_rel",
        column1="jet_template_metric_id",
        column2="environment_id",
        string="Environments",
        yaml_export="reference",
        help="Leave empty to apply to all environments",
    )

    _sql_constraints = [
        (
            "jet_template_metric_unique",
            "UNIQUE(jet_template_id, metric_id)",
            "A metric can be added to a Jet Template only once",
        ),
    ]

    def _get_pre_populated_model_data(self):
        """Check cx.tower.reference.mixin for the function documentation"""
        res = super()._get_pre_populated_model_data()
        res.update(
            {
                "cx.tower.jet.template.metric": [
                    "cx.tower.jet.template",
                    "jet_template_id",
                ]
            }
        )
        return res

    def _applies_to(self, jet):
        """Check if this template metric applies to a jet.

        Args:
            jet (cx.tower.jet()): Jet of the template.

        Returns:
            bool: True if no environments are set
                or the jet environment is one of them.
        """
        self.ensure_one()
        return not self.environment_ids or jet.environment_id in self.environment_ids
