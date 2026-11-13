# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError
from odoo.tools import mute_logger

from .common import TestMonitoringCommon


class TestMetricAccess(TestMonitoringCommon):
    """Access to metrics, thresholds and values."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server_value = cls.server_test_1.record_metric("test_load", value=1)
        cls.jet_value = cls.jet_sample.record_metric("test_load", value=2)
        cls.server_override = cls.MetricThreshold.create(
            {
                "metric_value_id": cls.server_value.id,
                "condition": ">=",
                "value_float": 5,
                "severity": "warning",
            }
        )
        cls.jet_override = cls.MetricThreshold.create(
            {
                "metric_value_id": cls.jet_value.id,
                "condition": ">=",
                "value_float": 5,
                "severity": "warning",
            }
        )
        cls.manager_2 = cls.Users.create(
            {
                "name": "Test Manager 2",
                "login": "test_metric_manager_2",
                "groups_id": [
                    (6, 0, [cls.group_manager.id, cls.env.ref("base.group_user").id])
                ],
            }
        )

    def _values_seen_by(self, user):
        """Return the values of this test a user can see.

        Other values (e.g. demo data) are left out.
        """
        test_values = self.server_value | self.jet_value
        return self.MetricValue.with_user(user).search([("id", "in", test_values.ids)])

    @mute_logger("odoo.addons.base.models.ir_model", "odoo.models")
    def test_user_has_no_access(self):
        """Users see no metrics, thresholds or values."""
        self.server_test_1.write({"user_ids": [(4, self.user.id)]})
        for model in (self.Metric, self.MetricThreshold, self.MetricValue):
            with self.assertRaises(AccessError):
                model.with_user(self.user).search([])

    def test_root_sees_all(self):
        """Root sees every value."""
        self.assertEqual(
            self._values_seen_by(self.root), self.server_value | self.jet_value
        )

    @mute_logger("odoo.addons.base.models.ir_rule")
    def test_manager_server_values(self):
        """Managers get the rights of the server on its values."""
        # Not linked to the server or the jet: nothing
        self.assertFalse(self._values_seen_by(self.manager))
        # Definition metrics and thresholds are visible to every Manager
        self.assertIn(self.metric_load, self.Metric.with_user(self.manager).search([]))
        self.assertIn(
            self.threshold_disk_warning,
            self.MetricThreshold.with_user(self.manager).search([]),
        )
        # Only Root changes them: their collectors and actions run everywhere
        with self.assertRaises(AccessError):
            self.metric_load.with_user(self.manager).write({"auto_sync_minutes": 5})
        with self.assertRaises(AccessError):
            self.Metric.with_user(self.manager).create(
                {"name": "Test Manager Metric", "widget": "number"}
            )
        with self.assertRaises(AccessError):
            self.threshold_disk_warning.with_user(self.manager).write(
                {"value_float": 70}
            )
        with self.assertRaises(AccessError):
            self.MetricThreshold.with_user(self.manager).create(
                {
                    "metric_id": self.metric_load.id,
                    "condition": ">=",
                    "value_float": 5,
                    "severity": "warning",
                }
            )

        # Server user: read only
        self.server_test_1.write({"user_ids": [(4, self.manager.id)]})
        self.assertEqual(self._values_seen_by(self.manager), self.server_value)
        thresholds = self.MetricThreshold.with_user(self.manager).search([])
        self.assertIn(self.server_override, thresholds)
        self.assertNotIn(self.jet_override, thresholds)
        server_as_manager = self.server_test_1.with_user(self.manager)
        with self.assertRaises(AccessError):
            server_as_manager.record_metric("test_load", value=3)
        with self.assertRaises(AccessError):
            self.server_override.with_user(self.manager).write({"value_float": 6})

        # Server manager: read and write
        self.server_test_1.write({"manager_ids": [(4, self.manager.id)]})
        server_as_manager.record_metric("test_load", value=3)
        self.assertEqual(self.server_value.value, 3)
        self.server_override.with_user(self.manager).write({"value_float": 6})

        # Another server manager cannot delete a value they did not create
        self.server_test_1.write({"manager_ids": [(4, self.manager_2.id)]})
        with self.assertRaises(AccessError):
            self.server_value.with_user(self.manager_2).unlink()

    @mute_logger("odoo.addons.base.models.ir_rule")
    def test_manager_cannot_move_value(self):
        """A value cannot be moved to a server the Manager cannot write."""
        self.server_test_1.write({"manager_ids": [(4, self.manager.id)]})
        other_server = self.Server.create(
            {
                "name": "Test Metric Other Server",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "host_key": "test_key",
                "os_id": self.os_debian_10.id,
                "user_ids": [(6, 0, self.manager.ids)],
                "manager_ids": [(6, 0, [])],
            }
        )
        with self.assertRaises(AccessError):
            self.server_value.with_user(self.manager).write(
                {"server_id": other_server.id}
            )

    @mute_logger("odoo.addons.base.models.ir_rule")
    def test_manager_cannot_move_override(self):
        """An override cannot become a metric threshold,
        or move to a value the Manager cannot write."""
        self.server_test_1.write({"manager_ids": [(4, self.manager.id)]})
        override = self.server_override.with_user(self.manager)
        with self.assertRaises(AccessError):
            override.write({"metric_value_id": False})
        with self.assertRaises(AccessError):
            override.write({"metric_value_id": self.jet_value.id})
        self.assertEqual(self.server_override.metric_value_id, self.server_value)

    @mute_logger("odoo.addons.base.models.ir_rule")
    def test_manager_jet_values(self):
        """Jet values need access to the jet and to its server."""
        self.jet_sample.write({"manager_ids": [(4, self.manager.id)]})
        # No access to the jet server yet
        self.assertFalse(self._values_seen_by(self.manager))

        self.server_test_1.write({"user_ids": [(4, self.manager.id)]})
        self.assertEqual(
            self._values_seen_by(self.manager), self.server_value | self.jet_value
        )
        self.jet_sample.with_user(self.manager).record_metric("test_load", value=4)
        self.assertEqual(self.jet_value.value, 4)
        self.jet_override.with_user(self.manager).write({"value_float": 6})

        # Jet user only: read, no write
        self.jet_sample.write(
            {
                "manager_ids": [(3, self.manager_2.id)],
                "user_ids": [(4, self.manager_2.id)],
            }
        )
        self.server_test_1.write({"user_ids": [(4, self.manager_2.id)]})
        self.assertIn(self.jet_value, self._values_seen_by(self.manager_2))
        with self.assertRaises(AccessError):
            self.jet_sample.with_user(self.manager_2).record_metric(
                "test_load", value=5
            )
