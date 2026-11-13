# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import operator

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

CONDITION_OPERATORS = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
}


class CxTowerMetricThreshold(models.Model):
    """Threshold of a metric.

    Without ``metric_value_id`` it is a definition threshold of the metric.
    With ``metric_value_id`` it overrides the definition thresholds
    for that server or jet value only.
    """

    _name = "cx.tower.metric.threshold"
    _inherit = ["cx.tower.reference.mixin", "cx.tower.yaml.mixin"]
    _description = "Cetmix Tower Metric Threshold"
    _order = "sequence, id"

    name = fields.Char(related="metric_id.name", readonly=True)
    metric_id = fields.Many2one(
        comodel_name="cx.tower.metric",
        required=True,
        index=True,
        ondelete="cascade",
        compute="_compute_metric_id",
        store=True,
        readonly=False,
        precompute=True,
    )
    metric_value_id = fields.Many2one(
        comodel_name="cx.tower.metric.value",
        string="Metric Value",
        index=True,
        ondelete="cascade",
        help="Leave empty for a metric threshold. "
        "Set to override the metric thresholds for one server or jet",
    )
    sequence = fields.Integer(default=10, yaml_export=True)
    condition = fields.Selection(
        selection=[
            (">=", ">="),
            ("<=", "<="),
            (">", ">"),
            ("<", "<"),
            ("==", "=="),
            ("stale", "Stale"),
        ],
        required=True,
        default=">=",
        yaml_export=True,
        help="Stale: the value was not updated in time. "
        "For progress bar metrics other conditions compare "
        "used / total in percent",
    )
    severity = fields.Selection(
        selection=[("warning", "Warning"), ("critical", "Critical")],
        yaml_export=True,
        help="Value severity while the condition matches",
    )
    value_float = fields.Float(
        string="Value",
        yaml_export=True,
        help="Value to compare with. For progress bar metrics: percent",
    )
    action = fields.Selection(
        selection=[
            ("none", "None"),
            ("command", "Run Command"),
            ("plan", "Run Flight Plan"),
        ],
        required=True,
        default="none",
        yaml_export=True,
        help="Run when the condition becomes matched",
    )
    command_id = fields.Many2one(
        comodel_name="cx.tower.command",
        yaml_export="include",
    )
    plan_id = fields.Many2one(
        comodel_name="cx.tower.plan",
        string="Flight Plan",
        yaml_export="include",
    )

    @api.depends("metric_value_id")
    def _compute_metric_id(self):
        """Override thresholds belong to the metric of their value."""
        for threshold in self:
            if threshold.metric_value_id:
                threshold.metric_id = threshold.metric_value_id.metric_id
            else:
                threshold.metric_id = threshold.metric_id

    def write(self, vals):
        """Check the write access to the new metric value.

        Record rules are checked before the write only. Clearing
        ``metric_value_id`` would turn an override into a metric
        threshold, which only Root can change.
        """
        res = super().write(vals)
        if "metric_value_id" in vals:
            self.check_access("write")
        return res

    @api.constrains("condition", "severity", "action", "command_id", "plan_id")
    def _check_threshold(self):
        """Check the values required by the condition and the action."""
        for threshold in self:
            if threshold.condition != "stale" and not threshold.severity:
                raise ValidationError(
                    _(
                        "Threshold of metric '%(metric)s' must have a severity.",
                        metric=threshold.metric_id.name,
                    )
                )
            if threshold.action == "command" and not threshold.command_id:
                raise ValidationError(
                    _(
                        "Threshold of metric '%(metric)s' must have a command.",
                        metric=threshold.metric_id.name,
                    )
                )
            if threshold.action == "plan" and not threshold.plan_id:
                raise ValidationError(
                    _(
                        "Threshold of metric '%(metric)s' must have a flight plan.",
                        metric=threshold.metric_id.name,
                    )
                )

    def _get_pre_populated_model_data(self):
        """Check cx.tower.reference.mixin for the function documentation"""
        res = super()._get_pre_populated_model_data()
        res.update({"cx.tower.metric.threshold": ["cx.tower.metric", "metric_id"]})
        return res

    def _is_matched(self, metric_value, now=None):
        """Check if the threshold condition matches a metric value.

        Args:
            metric_value (cx.tower.metric.value()): Value to check.
            now (datetime, optional): Current time for the stale check.

        Returns:
            bool: True if the condition matches.
        """
        self.ensure_one()
        if self.condition == "stale":
            return metric_value._is_stale(now=now)
        compare_function = CONDITION_OPERATORS[self.condition]
        return compare_function(metric_value._get_compared_value(), self.value_float)

    def _run_action(self, metric_value, previous_state):
        """Run the threshold command or flight plan for a metric value.

        The action runs on the server of the value,
        with ``jet`` set when the value belongs to a jet.

        Args:
            metric_value (cx.tower.metric.value()): Value that matched.
            previous_state (str): Value state before this update.
        """
        self.ensure_one()
        if self.action == "none":
            return
        server = metric_value.server_id or metric_value.jet_id.server_id
        jet = metric_value.jet_id or None
        variable_values = metric_value._get_metric_custom_values(
            threshold=self, previous_state=previous_state
        )
        if self.action == "command":
            server.run_command(
                self.command_id,
                jet=jet,
                log={},
                variable_values=variable_values,
                metric=metric_value.metric_id,
                metric_value=metric_value,
            )
        elif self.action == "plan":
            server.run_flight_plan(
                self.plan_id,
                jet=jet,
                plan_log={
                    "metric_id": metric_value.metric_id.id,
                    "metric_value_id": metric_value.id,
                },
                variable_values=variable_values,
            )
