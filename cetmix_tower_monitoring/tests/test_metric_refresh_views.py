# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from .common import TestMonitoringCommon


class TestMetricRefreshViews(TestMonitoringCommon):
    """Server and jet views are refreshed once per transaction."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server_2 = cls.Server.create(
            {
                "name": "Test Monitoring Refresh 2",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "host_key": "test_key",
            }
        )

    def _patch_new_cursor_refresh(self):
        """Mock the post-commit send, which opens a new cursor.

        Returns:
            unittest.mock._patch: Patch with autospec.
        """
        return patch.object(
            self.registry["cx.tower.metric.value"],
            "_refresh_views_with_new_cursor",
            autospec=True,
        )

    def _run_postcommit(self):
        """Run the post-commit hooks. Test cursors do not run them."""
        self.env.cr.postcommit.run()

    def test_one_refresh_for_several_metrics(self):
        """Several metrics of several servers and a jet: one refresh."""
        with self._patch_new_cursor_refresh() as refresh_mock:
            self.server_test_1.record_metric("test_load", value=1)
            self.server_test_1.record_metric("test_gauge", value=2)
            # A flushing savepoint runs pre-commit hooks:
            # it must not send a refresh or drop the collected ids.
            with self.env.cr.savepoint():
                self.server_2.record_metric("test_load", value=3)
            self.jet_sample.record_metric("test_load", value=4)
            refresh_mock.assert_not_called()

            self._run_postcommit()

        refresh_mock.assert_called_once()
        rec_ids_by_model = refresh_mock.call_args.args[2]
        self.assertEqual(
            rec_ids_by_model,
            {
                "cx.tower.server": {self.server_test_1.id, self.server_2.id},
                "cx.tower.jet": {self.jet_sample.id},
            },
        )

    def test_no_refresh_on_rollback(self):
        """A rolled-back transaction sends nothing."""
        with self._patch_new_cursor_refresh() as refresh_mock:
            self.server_test_1.record_metric("test_load", value=1)
            # What a real rollback does to the post-commit hooks
            self.env.cr.postcommit.clear()
            self._run_postcommit()
        refresh_mock.assert_not_called()

    def test_one_refresh_for_stale_cron(self):
        """The stale cron refreshes all servers it changed at once."""
        value_1 = self.server_test_1.record_metric("test_load", value=1)
        value_2 = self.server_2.record_metric("test_load", value=2)
        # Values recorded above are not part of this check
        self.env.cr.postcommit.clear()
        # Time passes: move last_update back in SQL, so the stored state
        # stays "ok" like in real use. An ORM write would recompute it.
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE cx_tower_metric_value"
            " SET last_update = last_update - interval '60 minutes'"
            " WHERE id IN %s",
            ((value_1 | value_2)._ids,),
        )
        (value_1 | value_2).invalidate_recordset()
        self.assertEqual(value_1.state, "ok")

        with self._patch_new_cursor_refresh() as refresh_mock:
            self.MetricValue._cron_check_stale()
            self._run_postcommit()

        self.assertEqual(value_1.state, "stale")
        refresh_mock.assert_called_once()
        self.assertEqual(
            refresh_mock.call_args.args[2]["cx.tower.server"],
            {self.server_test_1.id, self.server_2.id},
        )

    def test_refresh_sent_to_managers_kanban_and_list(self):
        """Managers and Root get a kanban and list refresh, Users do not."""
        with patch.object(
            self.registry["res.users"], "reload_views", autospec=True
        ) as reload_mock:
            self.MetricValue._refresh_views(
                {
                    "cx.tower.server": {self.server_2.id, self.server_test_1.id},
                    "cx.tower.jet": set(),
                }
            )

        reload_mock.assert_called_once()
        recipients = reload_mock.call_args.args[0]
        self.assertIn(self.manager, recipients)
        self.assertIn(self.root, recipients)
        self.assertNotIn(self.user, recipients)
        self.assertEqual(
            reload_mock.call_args.kwargs,
            {
                "model": "cx.tower.server",
                "view_types": ["kanban", "list"],
                "rec_ids": sorted([self.server_test_1.id, self.server_2.id]),
            },
        )
