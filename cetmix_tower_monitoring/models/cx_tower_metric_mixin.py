# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import math

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .cx_tower_metric_value import METRIC_STATE_RANKING, METRIC_STATE_SELECTION


class CxTowerMetricMixin(models.AbstractModel):
    """Metrics of a server or a jet.

    Inheriting models define ``metric_value_ids`` and
    ``kanban_metric_value_ids``: a One2many needs the inverse field
    of the model (``server_id`` or ``jet_id``), so it cannot be
    declared here.
    """

    _name = "cx.tower.metric.mixin"
    _description = "Cetmix Tower Metric Mixin"

    # Field of `cx.tower.metric.value` that points to this model
    _metric_value_field = None

    monitoring_state = fields.Selection(
        selection=METRIC_STATE_SELECTION,
        compute="_compute_monitoring_state",
        store=True,
        groups="cetmix_tower_base.group_manager",
        help="The worst state of the metrics",
    )
    # List row decorations cannot be restricted to groups,
    # and fields used in them must be readable by every user.
    # This field shows the state to Managers only.
    monitoring_decoration = fields.Selection(
        selection=METRIC_STATE_SELECTION,
        compute="_compute_monitoring_decoration",
        compute_sudo=True,
    )
    has_metric_collector = fields.Boolean(
        compute="_compute_has_metric_collector",
        groups="cetmix_tower_base.group_manager",
        help="At least one metric has a collector command or flight plan",
    )
    # Odoo 18 kanban cards cannot embed an x2many list: the kanban arch
    # parser reads the fields of the nested list as fields of the card model.
    # The card renders this data with QWeb instead.
    kanban_metric_data = fields.Json(
        compute="_compute_kanban_metric_data",
        groups="cetmix_tower_base.group_manager",
    )

    @api.depends("metric_value_ids.state")
    def _compute_monitoring_state(self):
        """Worst state of the metric values, ``unknown`` if none."""
        for record in self:
            states = record.metric_value_ids.mapped("state")
            record.monitoring_state = next(
                (state for state in METRIC_STATE_RANKING if state in states),
                "unknown",
            )

    @api.depends("monitoring_state")
    @api.depends_context("uid")
    def _compute_monitoring_decoration(self):
        """Monitoring state for Managers, empty for other users."""
        is_manager = self.env.user.has_group("cetmix_tower_base.group_manager")
        for record in self:
            record.monitoring_decoration = (
                record.monitoring_state if is_manager else False
            )

    @api.depends(
        "metric_value_ids.command_id",
        "metric_value_ids.plan_id",
        "metric_value_ids.metric_id.command_id",
        "metric_value_ids.metric_id.plan_id",
    )
    def _compute_has_metric_collector(self):
        for record in self:
            commands, plans = record._get_metric_collectors()
            record.has_metric_collector = bool(commands or plans)

    @api.depends(
        "kanban_metric_value_ids.value",
        "kanban_metric_value_ids.max_value",
        "kanban_metric_value_ids.state",
        "kanban_metric_value_ids.metric_id.name",
        "kanban_metric_value_ids.metric_id.unit",
        "kanban_metric_value_ids.metric_id.widget",
    )
    def _compute_kanban_metric_data(self):
        """Metric values shown on the kanban card.

        ``percent`` is set for progress bar metrics,
        False for the others (shown as a number).
        """
        for record in self:
            record.kanban_metric_data = [
                metric_value._get_kanban_data()
                for metric_value in record.kanban_metric_value_ids
            ]

    def _get_metric_run_target(self):
        """Return the server and the jet to run collectors and actions on.

        Returns:
            tuple: (cx.tower.server(), cx.tower.jet() or None)
        """
        raise NotImplementedError()

    def _get_metric_collectors(self):
        """Return the distinct resolved collectors of the metric values.

        Returns:
            tuple: (cx.tower.command(), cx.tower.plan())
        """
        self.ensure_one()
        commands = self.env["cx.tower.command"]
        plans = self.env["cx.tower.plan"]
        for metric_value in self.metric_value_ids:
            command, plan = metric_value._get_collector()
            commands |= command
            plans |= plan
        return commands, plans

    def record_metric(self, metric_reference, value=None, used=None, total=None):
        """Save the latest value of a metric for this server or jet.

        Progress bar metrics take ``used`` and ``total`` (``total > 0``).
        Gauge and number metrics take ``value``, gauge also an optional
        ``total``.

        Args:
            metric_reference (str): Metric reference.
            value (float, optional): Value of a gauge or number metric.
            used (float, optional): Used amount of a progress bar metric.
            total (float, optional): Total of a progress bar or gauge metric.

        Raises:
            ValidationError: unknown metric or wrong arguments.

        Returns:
            cx.tower.metric.value(): Updated value record.
        """
        self.ensure_one()
        metric = self.env["cx.tower.metric"].get_by_reference(metric_reference)
        if not metric:
            raise ValidationError(
                _("Metric '%(metric)s' not found.", metric=metric_reference)
            )
        sample_value, sample_max_value = self._parse_metric_sample(
            metric, value=value, used=used, total=total
        )

        # Apply pending template sync first (jets), so that a value
        # added from the Jet Template is found and updated
        self.flush_recordset(["metric_value_ids"])
        metric_value_obj = self.env["cx.tower.metric.value"]
        metric_value = metric_value_obj.search(
            [
                ("metric_id", "=", metric.id),
                (self._metric_value_field, "=", self.id),
            ],
            limit=1,
        )
        if not metric_value:
            metric_value = metric_value_obj.create(
                {"metric_id": metric.id, self._metric_value_field: self.id}
            )
        metric_value._record(sample_value, sample_max_value)
        return metric_value

    def _parse_metric_sample(self, metric, value=None, used=None, total=None):
        """Check the arguments of ``record_metric`` against the metric widget.

        Args:
            metric (cx.tower.metric()): Metric.
            value (float, optional): Value of a gauge or number metric.
            used (float, optional): Used amount of a progress bar metric.
            total (float, optional): Total of a progress bar or gauge metric.

        Raises:
            ValidationError: wrong arguments.

        Returns:
            tuple: (value, max_value)
        """
        try:
            if metric.widget == "progressbar":
                if used is None or total is None:
                    raise ValidationError(
                        _(
                            "Metric '%(metric)s' requires 'used' and 'total'.",
                            metric=metric.reference,
                        )
                    )
                sample = (float(used), float(total))
            elif value is None:
                raise ValidationError(
                    _("Metric '%(metric)s' requires 'value'.", metric=metric.reference)
                )
            elif metric.widget == "gauge" and total is not None:
                sample = (float(value), float(total))
            else:
                sample = (float(value), 0.0)
        except (TypeError, ValueError) as e:
            raise ValidationError(
                _(
                    "Metric '%(metric)s' values must be numbers: %(error)s",
                    metric=metric.reference,
                    error=e,
                )
            ) from e
        # float() accepts "nan" and "inf": no threshold can match them
        if not all(math.isfinite(number) for number in sample):
            raise ValidationError(
                _(
                    "Metric '%(metric)s' values must be finite numbers.",
                    metric=metric.reference,
                )
            )
        if metric.widget == "progressbar" and sample[1] <= 0:
            raise ValidationError(
                _(
                    "Metric '%(metric)s' requires 'total' greater than 0.",
                    metric=metric.reference,
                )
            )
        return sample

    def action_refresh_metrics(self):
        """Run each distinct collector of the metrics once.

        A collector shared by several metrics runs once.
        It is expected to call ``record_metric`` for every metric it serves.
        """
        for record in self:
            server, jet = record._get_metric_run_target()
            commands, plans = record._get_metric_collectors()
            for command in commands:
                server.run_command(command, jet=jet, log={})
            for plan in plans:
                server.run_flight_plan(plan, jet=jet)
