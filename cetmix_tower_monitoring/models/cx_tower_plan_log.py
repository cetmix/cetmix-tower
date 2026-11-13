# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class CxTowerPlanLog(models.Model):
    _inherit = "cx.tower.plan.log"

    metric_id = fields.Many2one(
        comodel_name="cx.tower.metric",
        ondelete="set null",
        compute="_compute_metric",
        store=True,
        readonly=False,
        recursive=True,
        help="Metric whose threshold runs this flight plan",
    )
    metric_value_id = fields.Many2one(
        comodel_name="cx.tower.metric.value",
        ondelete="set null",
        compute="_compute_metric",
        store=True,
        readonly=False,
        recursive=True,
        help="Metric value whose threshold runs this flight plan",
    )
    metric_auto_sync = fields.Boolean(
        index=True,
        help="Started by metric auto sync. Deleted when the run is done",
    )

    @api.depends(
        "parent_flight_plan_log_id.metric_id",
        "parent_flight_plan_log_id.metric_value_id",
    )
    def _compute_metric(self):
        """Nested flight plans take the metric of the parent flight plan."""
        for plan_log in self:
            parent_log = plan_log.parent_flight_plan_log_id
            if parent_log:
                plan_log.update(
                    {
                        "metric_id": parent_log.metric_id,
                        "metric_value_id": parent_log.metric_value_id,
                    }
                )
            else:
                plan_log.update(
                    {
                        "metric_id": plan_log.metric_id,
                        "metric_value_id": plan_log.metric_value_id,
                    }
                )

    def record(self, server, plan, status, **kwargs):
        """Keep the log of a refused auto sync run.

        ``record()`` logs a run that did not start (e.g. another instance
        is running). The log explains why the values are not updated.
        """
        plan_log_vals = kwargs.get("plan_log")
        if plan_log_vals:
            kwargs["plan_log"] = dict(plan_log_vals, metric_auto_sync=False)
        return super().record(server, plan, status, **kwargs)
