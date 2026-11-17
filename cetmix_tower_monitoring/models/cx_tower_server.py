# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CxTowerServer(models.Model):
    _name = "cx.tower.server"
    _inherit = ["cx.tower.server", "cx.tower.metric.mixin"]

    _metric_value_field = "server_id"

    monitoring_pull_data = fields.Boolean(
        string="Pull data",
        tracking=True,
        groups="cetmix_tower_base.group_manager",
        help="Pull metric data of this server and its jets on schedule, "
        "for metrics with 'Pull data, minutes' set",
    )

    metric_value_ids = fields.One2many(
        comodel_name="cx.tower.metric.value",
        inverse_name="server_id",
        string="Metrics",
        groups="cetmix_tower_base.group_manager",
    )
    kanban_metric_value_ids = fields.One2many(
        comodel_name="cx.tower.metric.value",
        inverse_name="server_id",
        string="Kanban Metrics",
        domain=[("metric_id.show_on_kanban", "=", True)],
        groups="cetmix_tower_base.group_manager",
    )

    def _get_metric_run_target(self):
        """Check cx.tower.metric.mixin for the function documentation"""
        self.ensure_one()
        return self, None
