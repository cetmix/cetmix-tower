# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CxTowerCommandLog(models.Model):
    _inherit = "cx.tower.command.log"

    metric_auto_sync = fields.Boolean(
        index=True,
        help="Started by metric auto sync. Deleted when the run is done",
    )

    def record(self, server_id, command_id, *args, **kwargs):
        """Keep the log of a refused auto sync run.

        ``record()`` logs a run that did not start (e.g. another instance
        is running). The log explains why the values are not updated.
        """
        if kwargs.get("metric_auto_sync"):
            kwargs["metric_auto_sync"] = False
        return super().record(server_id, command_id, *args, **kwargs)
