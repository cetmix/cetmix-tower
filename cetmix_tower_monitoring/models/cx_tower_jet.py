# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command, api, fields, models


class CxTowerJet(models.Model):
    _name = "cx.tower.jet"
    _inherit = ["cx.tower.jet", "cx.tower.metric.mixin"]

    _metric_value_field = "jet_id"

    metric_value_ids = fields.One2many(
        comodel_name="cx.tower.metric.value",
        inverse_name="jet_id",
        string="Metrics",
        groups="cetmix_tower_base.group_manager",
        compute="_compute_metric_value_ids",
        store=True,
        readonly=False,
    )
    kanban_metric_value_ids = fields.One2many(
        comodel_name="cx.tower.metric.value",
        inverse_name="jet_id",
        string="Kanban Metrics",
        domain=[("metric_id.show_on_kanban", "=", True)],
        groups="cetmix_tower_base.group_manager",
    )

    # Do not depend on `metric_value_ids`: this compute writes it.
    @api.depends(
        "jet_template_id.metric_ids.metric_id",
        "jet_template_id.metric_ids.environment_ids",
        "environment_id",
    )
    def _compute_metric_value_ids(self):
        """Sync the metric values of the jet with its Jet Template.

        Manual values are never changed. Template values whose metric
        no longer applies are deleted, and applicable metrics without
        any value get a template value.
        """
        for jet in self:
            template_metrics = jet.jet_template_id.metric_ids.filtered(
                lambda template_metric, jet=jet: template_metric._applies_to(jet)
            ).metric_id
            commands = [
                Command.unlink(metric_value.id)
                for metric_value in jet.metric_value_ids
                if not metric_value.manual
                and metric_value.metric_id not in template_metrics
            ]
            existing_metrics = jet.metric_value_ids.metric_id
            commands += [
                Command.create({"metric_id": metric.id, "manual": False})
                for metric in template_metrics
                if metric not in existing_metrics
            ]
            jet.metric_value_ids = commands

    def _get_metric_run_target(self):
        """Check cx.tower.metric.mixin for the function documentation"""
        self.ensure_one()
        return self.server_id, self
