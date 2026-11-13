# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
from collections import defaultdict
from datetime import timedelta

from odoo import SUPERUSER_ID, Command, _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.modules.registry import Registry

_logger = logging.getLogger(__name__)

# Worst first
METRIC_STATE_RANKING = ["critical", "stale", "warning", "unknown", "ok"]

METRIC_STATE_SELECTION = [
    ("unknown", "Unknown"),
    ("ok", "OK"),
    ("warning", "Warning"),
    ("critical", "Critical"),
    ("stale", "Stale"),
]

# Precommit data key: ids of the servers and jets whose views must be refreshed
REFRESH_VIEWS_KEY = "cetmix_tower_monitoring.refresh_views"


class CxTowerMetricValue(models.Model):
    """Latest sample of a metric on a server or a jet. No history."""

    _name = "cx.tower.metric.value"
    _description = "Cetmix Tower Metric Value"
    _order = "metric_id, id"

    metric_id = fields.Many2one(
        comodel_name="cx.tower.metric",
        required=True,
        index=True,
        ondelete="cascade",
    )
    name = fields.Char(related="metric_id.name")
    unit = fields.Char(related="metric_id.unit")
    widget = fields.Selection(related="metric_id.widget")
    server_id = fields.Many2one(
        comodel_name="cx.tower.server",
        index=True,
        ondelete="cascade",
    )
    jet_id = fields.Many2one(
        comodel_name="cx.tower.jet",
        index=True,
        ondelete="cascade",
    )
    value = fields.Float(readonly=True, help="Current value")
    max_value = fields.Float(
        string="Total",
        readonly=True,
        help="Total or maximum value",
    )
    last_update = fields.Datetime(readonly=True)
    manual = fields.Boolean(
        default=True,
        help="Added by a user or by record_metric(). "
        "Values added from the Jet Template are not manual",
    )
    last_auto_sync = fields.Datetime(
        readonly=True,
        help="When the last auto sync run for this value started",
    )
    state = fields.Selection(
        selection=METRIC_STATE_SELECTION,
        compute="_compute_state",
        store=True,
    )
    command_id = fields.Many2one(
        comodel_name="cx.tower.command",
        string="Collector Command",
        help="Overrides the collector of the metric for this server or jet",
    )
    plan_id = fields.Many2one(
        comodel_name="cx.tower.plan",
        string="Collector Flight Plan",
        help="Overrides the collector of the metric for this server or jet",
    )
    threshold_ids = fields.One2many(
        comodel_name="cx.tower.metric.threshold",
        inverse_name="metric_value_id",
        help="Override thresholds. "
        "If set, the metric thresholds are not used for this value",
    )
    active_threshold_ids = fields.Many2many(
        comodel_name="cx.tower.metric.threshold",
        relation="cx_tower_metric_value_active_threshold_rel",
        column1="metric_value_id",
        column2="threshold_id",
        string="Matching Thresholds",
        readonly=True,
    )

    _sql_constraints = [
        (
            "server_or_jet",
            "CHECK((server_id IS NULL) != (jet_id IS NULL))",
            "A metric value belongs to exactly one server or one jet",
        ),
        (
            "metric_server_unique",
            "UNIQUE(metric_id, server_id)",
            "A server can have only one value per metric",
        ),
        (
            "metric_jet_unique",
            "UNIQUE(metric_id, jet_id)",
            "A jet can have only one value per metric",
        ),
    ]

    @api.depends(
        "last_update",
        "metric_id.stale_after_minutes",
        "active_threshold_ids.condition",
        "active_threshold_ids.severity",
    )
    def _compute_state(self):
        """Compute the value state.

        1. unknown: no sample yet
        2. stale: the sample is too old
        3. the worst severity of the matching thresholds
        4. ok
        """
        now = fields.Datetime.now()
        for metric_value in self:
            if not metric_value.last_update:
                metric_value.state = "unknown"
            elif metric_value._is_stale(now=now):
                metric_value.state = "stale"
            else:
                severities = metric_value.active_threshold_ids.filtered(
                    lambda threshold: threshold.condition != "stale"
                ).mapped("severity")
                if "critical" in severities:
                    metric_value.state = "critical"
                elif "warning" in severities:
                    metric_value.state = "warning"
                else:
                    metric_value.state = "ok"

    def write(self, vals):
        """Check the write access to the new server or jet.

        Record rules are checked before the write only,
        so moving a value to another server or jet is checked here.
        """
        res = super().write(vals)
        if "server_id" in vals or "jet_id" in vals:
            self.check_access("write")
        return res

    @api.constrains("command_id", "plan_id")
    def _check_collector(self):
        """A value is collected by a command or a flight plan, not both."""
        for metric_value in self:
            if metric_value.command_id and metric_value.plan_id:
                raise ValidationError(
                    _(
                        "Metric value '%(metric)s' cannot have both a collector "
                        "command and a collector flight plan.",
                        metric=metric_value.metric_id.name,
                    )
                )

    def _is_stale(self, now=None):
        """Check if the latest sample is older than the metric allows.

        Args:
            now (datetime, optional): Current time.

        Returns:
            bool: True if the value is stale.
        """
        self.ensure_one()
        if not self.last_update:
            return False
        now = now or fields.Datetime.now()
        stale_limit = now - timedelta(minutes=self.metric_id.stale_after_minutes)
        return self.last_update < stale_limit

    def _has_pending_stale_threshold(self):
        """Check if a stale threshold of the value has not matched yet.

        Returns:
            bool: True if a resolved stale threshold is not active.
        """
        self.ensure_one()
        return any(
            threshold.condition == "stale"
            and threshold not in self.active_threshold_ids
            for threshold in self._get_thresholds()
        )

    def _get_compared_value(self):
        """Return the number thresholds compare against.

        Progress bar metrics compare used / total in percent.
        Other metrics compare the value.

        Returns:
            float: Value to compare.
        """
        self.ensure_one()
        if self.widget == "progressbar" and self.max_value:
            return self.value / self.max_value * 100
        return self.value

    def _get_kanban_data(self):
        """Return the value as shown on a server or jet kanban card.

        Returns:
            dict: ``name``, ``label`` (value, total and unit), ``state``
                and ``percent`` (used / total in percent for progress bar
                metrics, False for the others: they are shown as a number).
        """
        self.ensure_one()
        value = f"{round(self.value, 2):g}"
        if self.widget == "progressbar" and self.max_value > 0:
            label = f"{value} / {round(self.max_value, 2):g}"
            percent = min(self.value / self.max_value * 100, 100)
        else:
            label = value
            percent = False
        if self.unit:
            label = f"{label} {self.unit}"
        return {
            "name": self.name,
            "label": label,
            "state": self.state,
            "percent": percent,
        }

    def _get_collector(self):
        """Return the resolved collector.

        The collector of the value if it has one, else the metric one.

        Returns:
            tuple: (cx.tower.command(), cx.tower.plan())
        """
        self.ensure_one()
        if self.command_id or self.plan_id:
            return self.command_id, self.plan_id
        return self.metric_id.command_id, self.metric_id.plan_id

    def _get_thresholds(self):
        """Return the resolved thresholds.

        The override thresholds of the value if it has any,
        else the definition thresholds of the metric.

        Returns:
            cx.tower.metric.threshold(): Thresholds
        """
        self.ensure_one()
        return self.threshold_ids or self.metric_id.threshold_ids

    def _record(self, value, max_value):
        """Save a new sample and evaluate the thresholds.

        Args:
            value (float): Current value.
            max_value (float): Total or maximum value.
        """
        self.ensure_one()
        previous_state = self.state
        self.write(
            {
                "value": value,
                "max_value": max_value,
                "last_update": fields.Datetime.now(),
            }
        )
        self._evaluate_thresholds(previous_state)
        self._refresh_views_on_commit()

    def _refresh_views_on_commit(self):
        """Refresh the server and jet views of these values once, after commit.

        All values updated in the same transaction (several metrics,
        several servers and jets, e.g. by a cron) are collected and
        refreshed together once the transaction is committed.
        Nothing is sent if the transaction is rolled back.

        Post-commit, not pre-commit: every flushing savepoint runs the
        pre-commit hooks and a rolled-back one clears them
        (``odoo/sql_db.py``, ``_FlushingSavepoint``), which would send
        several refreshes per transaction or lose some.
        """
        if not self:
            return
        postcommit = self.env.cr.postcommit
        if REFRESH_VIEWS_KEY not in postcommit.data:
            postcommit.data[REFRESH_VIEWS_KEY] = {
                "cx.tower.server": set(),
                "cx.tower.jet": set(),
            }
            dbname = self.env.cr.dbname

            @postcommit.add
            def refresh_views():
                self._refresh_views_with_new_cursor(
                    dbname, postcommit.data.pop(REFRESH_VIEWS_KEY, {})
                )

        rec_ids_by_model = postcommit.data[REFRESH_VIEWS_KEY]
        rec_ids_by_model["cx.tower.server"].update(self.server_id.ids)
        rec_ids_by_model["cx.tower.jet"].update(self.jet_id.ids)

    @api.model
    def _refresh_views_with_new_cursor(self, dbname, rec_ids_by_model):
        """Send the refresh from a new cursor.

        Runs after commit, when the current transaction is closed.
        Same pattern as ``mail.mail.send_after_commit``.

        Args:
            dbname (str): Database name.
            rec_ids_by_model (dict): {model name: set of record ids}
        """
        if not any(rec_ids_by_model.values()):
            return
        with Registry(dbname).cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            env["cx.tower.metric.value"]._refresh_views(rec_ids_by_model)

    @api.model
    def _refresh_views(self, rec_ids_by_model):
        """Refresh the server and jet kanban and list views.

        Sent to every Tower Manager: values are often updated by a cron,
        a webhook or a queued job, not by the user who looks at them.
        Only kanban and list views are refreshed: a form reload drops
        unsaved changes. The client reloads a view only when it shows
        one of the records.

        Args:
            rec_ids_by_model (dict): {model name: set of record ids}
        """
        managers = (
            self.env["res.users"]
            .sudo()
            .search(
                [
                    (
                        "groups_id",
                        "in",
                        [
                            self.env.ref("cetmix_tower_base.group_manager").id,
                            self.env.ref("cetmix_tower_base.group_root").id,
                        ],
                    ),
                    ("share", "=", False),
                ]
            )
        )
        for model, rec_ids in rec_ids_by_model.items():
            if rec_ids:
                managers.reload_views(
                    model=model,
                    view_types=["kanban", "list"],
                    rec_ids=sorted(rec_ids),
                )

    def _evaluate_thresholds(self, previous_state, now=None):
        """Update the matching thresholds and run newly matched ones.

        A threshold action runs only when the threshold becomes matched,
        not on every sample while it stays matched.

        Args:
            previous_state (str): Value state before this update.
            now (datetime, optional): Current time for the stale check.
        """
        self.ensure_one()
        matching_thresholds = self._get_thresholds().filtered(
            lambda threshold: threshold._is_matched(self, now=now)
        )
        new_thresholds = matching_thresholds - self.active_threshold_ids
        self.write({"active_threshold_ids": [Command.set(matching_thresholds.ids)]})
        for threshold in new_thresholds:
            threshold._run_action(self, previous_state)

    def _get_metric_custom_values(self, threshold, previous_state):
        """Return custom values for threshold actions.

        Used by SSH commands and flight plan conditions,
        where Python objects are not available.

        Args:
            threshold (cx.tower.metric.threshold()): Threshold that matched.
            previous_state (str): Value state before this update.

        Returns:
            dict: Custom values.
        """
        self.ensure_one()
        server = self.server_id or self.jet_id.server_id
        return {
            "__metric__": self.metric_id.reference,
            "__metric_value__": str(self.value),
            "__metric_max__": str(self.max_value) if self.max_value else "",
            "__metric_unit__": self.unit or "",
            "__metric_state__": self.state,
            "__metric_previous_state__": previous_state or "",
            "__metric_severity__": threshold.severity or "",
            "__server__": server.reference,
            "__jet__": self.jet_id.reference or "",
        }

    def _rearm_stale_thresholds(self):
        """Clear the active stale thresholds of values that are fresh.

        A longer ``stale_after_minutes`` can make a stale value fresh
        without a new sample. Its stale thresholds must run again
        when the value becomes stale again.
        """
        now = fields.Datetime.now()
        for metric_value in self:
            if metric_value._is_stale(now=now):
                continue
            stale_thresholds = metric_value.active_threshold_ids.filtered(
                lambda threshold: threshold.condition == "stale"
            )
            if stale_thresholds:
                metric_value.write(
                    {
                        "active_threshold_ids": [
                            Command.unlink(threshold.id)
                            for threshold in stale_thresholds
                        ]
                    }
                )

    @api.model
    def _cron_check_stale(self):
        """Mark values that are no longer updated as stale.

        ``state`` depends on the current time, and time alone triggers
        no recompute. Mark ``last_update`` as modified to recompute
        ``state`` and the parent ``monitoring_state``,
        then run stale thresholds that just matched.

        A value can already be stale without its stale thresholds run:
        ``state`` is also recomputed when ``stale_after_minutes``
        changes. Such values are selected too.
        """
        now = fields.Datetime.now()
        metric_values = self.search([("last_update", "!=", False)]).filtered(
            lambda metric_value: metric_value._is_stale(now=now)
            and (
                metric_value.state != "stale"
                or metric_value._has_pending_stale_threshold()
            )
        )
        if not metric_values:
            return
        previous_states = {
            metric_value.id: metric_value.state for metric_value in metric_values
        }
        metric_values.filtered(
            lambda metric_value: metric_value.state != "stale"
        ).modified(["last_update"])
        self.env.flush_all()
        for metric_value in metric_values:
            metric_value._evaluate_thresholds(previous_states[metric_value.id], now=now)
        metric_values._refresh_views_on_commit()

    @api.model
    def _cron_auto_sync(self):
        """Run the collectors of values whose metric has auto sync.

        Each distinct collector runs once per server or jet, the same way
        as Refresh. The logs of these runs are deleted when they are done:
        runs done in Odoo right after they return, queued runs on a later
        cron run.
        """
        self._delete_metric_auto_sync_logs()
        now = fields.Datetime.now()
        metric_values = self.search([("metric_id.auto_sync_minutes", ">", 0)])
        due_values = metric_values.filtered(
            lambda metric_value: not metric_value.last_auto_sync
            or metric_value.last_auto_sync
            <= now - timedelta(minutes=metric_value.metric_id.auto_sync_minutes)
        )
        values_by_run = defaultdict(lambda: self.browse())
        for metric_value in due_values:
            command, plan = metric_value._get_collector()
            if not command and not plan:
                continue
            server = metric_value.server_id or metric_value.jet_id.server_id
            run_key = (server, metric_value.jet_id, command, plan)
            values_by_run[run_key] |= metric_value

        synced_values = self.browse()
        for (server, jet, command, plan), run_values in values_by_run.items():
            # A failing collector must not stop the others.
            # Its values still wait N minutes before the next attempt.
            try:
                with self.env.cr.savepoint():
                    if command:
                        server.run_command(
                            command, jet=jet or None, log={"metric_auto_sync": True}
                        )
                    else:
                        server.run_flight_plan(
                            plan, jet=jet or None, plan_log={"metric_auto_sync": True}
                        )
            except Exception as e:  # pylint: disable=broad-exception-caught
                _logger.exception(
                    "Metric auto sync of '%s' on '%s' failed: %s",
                    (command or plan).name,
                    (jet or server).name,
                    e,
                )
            synced_values |= run_values
        if synced_values:
            synced_values.write({"last_auto_sync": now})
            self._delete_metric_auto_sync_logs()

    @api.model
    def _delete_metric_auto_sync_logs(self):
        """Delete the logs of finished auto sync runs.

        Logs are not deleted while the run is in progress: code that is
        still running reads them. Command logs of flight plan lines and
        nested flight plan logs are deleted with their flight plan log
        (ondelete cascade). Flight plans started by a deleted command log
        are deleted too. Logs of threshold actions are separate runs
        and are kept.
        """
        command_logs = (
            self.env["cx.tower.command.log"]
            .sudo()
            .search(
                [
                    ("metric_auto_sync", "=", True),
                    ("plan_log_id", "=", False),
                    ("finish_date", "!=", False),
                ]
            )
        )
        plan_log_obj = self.env["cx.tower.plan.log"].sudo()
        plan_logs = plan_log_obj.search(
            [
                ("metric_auto_sync", "=", True),
                ("parent_flight_plan_log_id", "=", False),
                ("finish_date", "!=", False),
            ]
        )
        if command_logs:
            plan_logs |= plan_log_obj.search(
                [("triggering_command_log_id", "in", command_logs.ids)]
            )
        plan_logs.unlink()
        command_logs.unlink()
