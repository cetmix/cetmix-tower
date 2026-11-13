# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class CxTowerPlan(models.Model):
    _inherit = "cx.tower.plan"

    def _run_single(self, server, jet_template=None, jet=None, **kwargs):
        """Save the metric of the run on the flight plan log.

        A threshold command that runs a flight plan passes the metric
        as kwargs. They reach the first line only: the other lines read
        the metric from the flight plan log.
        """
        metric = kwargs.get("metric")
        metric_value = kwargs.get("metric_value")
        if metric or metric_value:
            plan_log_vals = dict(kwargs.get("plan_log") or {})
            if metric:
                plan_log_vals.setdefault("metric_id", metric.id)
            if metric_value:
                plan_log_vals.setdefault("metric_value_id", metric_value.id)
            kwargs["plan_log"] = plan_log_vals
        return super()._run_single(server, jet_template=jet_template, jet=jet, **kwargs)
