# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command, fields, models


class CxTowerServerTemplate(models.Model):
    _inherit = "cx.tower.server.template"

    metric_ids = fields.Many2many(
        comodel_name="cx.tower.metric",
        string="Metrics",
        groups="cetmix_tower_base.group_manager",
        yaml_export="reference",
        help="Servers created from this template get these metrics",
    )

    def _prepare_server_values(self, *args, **kwargs):
        """Add a value for each metric of the template.

        Metrics are copied once, when the server is created.
        """
        values = super()._prepare_server_values(*args, **kwargs)
        values["metric_value_ids"] = [
            Command.create({"metric_id": metric.id}) for metric in self.metric_ids
        ]
        return values
