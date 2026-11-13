# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CxTowerMetric(models.Model):
    """Metric definition: what is measured and how it is collected."""

    _name = "cx.tower.metric"
    _inherit = ["cx.tower.reference.mixin", "cx.tower.yaml.mixin"]
    _description = "Cetmix Tower Metric"
    _order = "name"

    name = fields.Char(yaml_export=True)
    active = fields.Boolean(default=True, yaml_export=True)
    unit = fields.Char(
        yaml_export=True,
        help="Unit shown next to the value, e.g. GiB or %",
    )
    note = fields.Text(
        yaml_export=True,
        help="Detailed description of the metric: what is measured and how",
    )
    widget = fields.Selection(
        selection=[
            ("progressbar", "Progress Bar"),
            ("gauge", "Gauge"),
            ("number", "Number"),
        ],
        required=True,
        default="number",
        yaml_export=True,
        help="Progress Bar: used of total. "
        "Gauge: value, with an optional maximum. "
        "Number: plain value.",
    )
    show_on_kanban = fields.Boolean(
        default=True,
        yaml_export=True,
        help="Show this metric on the server and jet kanban cards",
    )
    stale_after_minutes = fields.Integer(
        required=True,
        default=30,
        yaml_export=True,
        help="A value not updated for this many minutes becomes stale",
    )
    auto_sync_minutes = fields.Integer(
        string="Auto sync, minutes",
        default=0,
        yaml_export=True,
        help="Run the collector of every value of this metric every N minutes. "
        "0 = off, otherwise at least 5. The check runs every 5 minutes, "
        "so the real interval can be up to 5 minutes longer",
    )
    command_id = fields.Many2one(
        comodel_name="cx.tower.command",
        string="Collector Command",
        yaml_export="include",
        help="Command that collects this metric. "
        "It must call record_metric() for this metric",
    )
    plan_id = fields.Many2one(
        comodel_name="cx.tower.plan",
        string="Collector Flight Plan",
        yaml_export="include",
        help="Flight plan that collects this metric. "
        "It must call record_metric() for this metric",
    )
    threshold_ids = fields.One2many(
        comodel_name="cx.tower.metric.threshold",
        inverse_name="metric_id",
        domain=[("metric_value_id", "=", False)],
        yaml_export="explode",
    )
    value_ids = fields.One2many(
        comodel_name="cx.tower.metric.value",
        inverse_name="metric_id",
    )

    def write(self, vals):
        """Rearm stale thresholds when a longer interval makes values fresh."""
        res = super().write(vals)
        if "stale_after_minutes" in vals:
            self.value_ids._rearm_stale_thresholds()
        return res

    @api.constrains("auto_sync_minutes")
    def _check_auto_sync_minutes(self):
        """Auto sync is off (0) or runs at most every 5 minutes."""
        for metric in self:
            if metric.auto_sync_minutes and metric.auto_sync_minutes < 5:
                raise ValidationError(
                    _(
                        "Metric '%(metric)s': auto sync must be 0 (off)"
                        " or at least 5 minutes.",
                        metric=metric.name,
                    )
                )

    @api.constrains("command_id", "plan_id")
    def _check_collector(self):
        """A metric is collected by a command or a flight plan, not both."""
        for metric in self:
            if metric.command_id and metric.plan_id:
                raise ValidationError(
                    _(
                        "Metric '%(metric)s' cannot have both a collector "
                        "command and a collector flight plan.",
                        metric=metric.name,
                    )
                )

    def _get_dependent_model_relation_fields(self):
        """Check cx.tower.reference.mixin for the function documentation"""
        res = super()._get_dependent_model_relation_fields()
        return res + ["threshold_ids"]
