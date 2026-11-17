# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class CxTowerPlanLine(models.Model):
    _inherit = "cx.tower.plan.line"

    def _run(self, server, plan_log_record, **kwargs):
        """Pass the metric of the flight plan log to every line.

        A flight plan passes its run kwargs to the first line only,
        so the metric is read back from the flight plan log.
        """
        if plan_log_record.metric_id:
            kwargs["metric"] = plan_log_record.metric_id.with_env(server.env)
        if plan_log_record.metric_value_id:
            kwargs["metric_value"] = plan_log_record.metric_value_id.with_env(
                server.env
            )
        return super()._run(server, plan_log_record, **kwargs)
