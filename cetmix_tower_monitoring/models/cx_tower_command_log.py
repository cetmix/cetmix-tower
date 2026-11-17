# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CxTowerCommandLog(models.Model):
    _inherit = "cx.tower.command.log"

    metric_pull_data = fields.Boolean(
        index=True,
        help="Started by metric data pull. Deleted when the run is done",
    )

    def record(self, server_id, command_id, *args, **kwargs):
        """Keep the log of a refused data pull run.

        ``record()`` logs a run that did not start (e.g. another instance
        is running). The log explains why the values are not updated.
        """
        if kwargs.get("metric_pull_data"):
            kwargs["metric_pull_data"] = False
        return super().record(server_id, command_id, *args, **kwargs)
