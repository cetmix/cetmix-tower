# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, models


class CxTowerCommand(models.Model):
    _inherit = "cx.tower.command"

    def _get_python_command_odoo_objects(
        self, server=None, jet_template=None, jet=None, waypoint=None, **kwargs
    ):
        """Add the metric of a threshold run to the evaluation context.

        ``metric`` and ``metric_value`` are None when the command
        is not run by a metric threshold.
        """
        res = super()._get_python_command_odoo_objects(
            server=server,
            jet_template=jet_template,
            jet=jet,
            waypoint=waypoint,
            **kwargs,
        )
        res.update(
            {
                "metric": {
                    "import": kwargs.get("metric"),
                    "help": _("Cetmix Tower metric whose threshold runs this command"),
                },
                "metric_value": {
                    "import": kwargs.get("metric_value"),
                    "help": _(
                        "Current Cetmix Tower metric value whose threshold "
                        "runs this command"
                    ),
                },
                "tower_metrics": {
                    "import": self.env["cx.tower.metric"],
                    "help": _(
                        "A helper shortcut to <code>env['cx.tower.metric']</code>"
                    ),
                },
                "tower_metric_values": {
                    "import": self.env["cx.tower.metric.value"],
                    "help": _(
                        "A helper shortcut to "
                        "<code>env['cx.tower.metric.value']</code>"
                    ),
                },
            }
        )
        return res
