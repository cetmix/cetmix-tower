# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from datetime import timedelta
from unittest.mock import MagicMock, patch

from psycopg2.errors import LockNotAvailable, SerializationFailure

from odoo.fields import Datetime
from odoo.tools import mute_logger

from ..models.constants import COMMAND_STOPPED, COMMAND_TIMED_OUT
from .common import TestTowerCommon


class TestTowerCommandDefer(TestTowerCommon):
    """Tests for async runner hooks: defer handlers, SSH helpers, finish."""

    def test_default_handlers_run_command_runner(self):
        """An empty handler list still runs the in-Odoo command runner."""
        with self._patch_defer_handlers([]):
            self.server_test_1.run_command(self.command_create_dir)
        log = self.CommandLog.search(
            [("command_id", "=", self.command_create_dir.id)],
            order="id desc",
            limit=1,
        )
        self.assertFalse(log.is_running)
        self.assertEqual(log.command_status, 0)

    def test_sequence_10_handler_wins_over_50(self):
        """First True handler wins; a later sequence is not called."""
        handler_10 = MagicMock(return_value=True)
        handler_50 = MagicMock(return_value=True)
        with (
            self._patch_defer_handlers([(50, handler_50), (10, handler_10)]),
            patch.object(
                self.registry["cx.tower.server"],
                "_command_runner_ssh",
            ) as ssh_runner,
        ):
            self.server_test_1.run_command(self.command_create_dir)
            ssh_runner.assert_not_called()
        handler_10.assert_called()
        handler_50.assert_not_called()
        log = self.CommandLog.search(
            [("command_id", "=", self.command_create_dir.id)],
            order="id desc",
            limit=1,
        )
        self.assertTrue(log.is_running)

    def test_prepare_ssh_execution_sudo_and_secrets(self):
        """sudo n is a string, sudo p is a list; secrets are replaced."""
        server = self.server_test_1
        secret_code = f"echo #!cxtower.secret.{self.secret_2.reference}!#"
        key_kwargs = {"key": {"server_id": server.id}}

        prepared_n = server._prepare_ssh_execution(secret_code, sudo="n", **key_kwargs)
        self.assertIsInstance(prepared_n["commands"], str)
        self.assertIn(self.sudo_prefix, prepared_n["commands"])
        self.assertIn("secret top", prepared_n["commands"])
        self.assertNotIn("#!cxtower.secret", prepared_n["commands"])
        self.assertIn("secret top", prepared_n["key_values"])

        prepared_p = server._prepare_ssh_execution(secret_code, sudo="p", **key_kwargs)
        self.assertIsInstance(prepared_p["commands"], list)
        self.assertIn("secret top", prepared_p["commands"][0])
        self.assertIn("secret top", prepared_p["key_values"])

    def test_get_ssh_connection_values_no_socket(self):
        """host_key is omitted when skip_host_key; password comes from vault."""
        with patch("socket.create_connection") as create_conn:
            self.server_test_1.skip_host_key = True
            values = self.server_test_1._get_ssh_connection_values()
            self.assertIsNone(values["host_key"])
            self.assertTrue(values["skip_host_key"])
            self.assertEqual(values["password"], "password")
            self.assertEqual(values["host"], "localhost")
            self.assertEqual(values["username"], "admin")
            self.assertEqual(values["auth_mode"], "p")

            self.server_test_1.skip_host_key = False
            values_skip_arg = self.server_test_1._get_ssh_connection_values(
                skip_host_key=True
            )
            self.assertIsNone(values_skip_arg["host_key"])
            self.assertTrue(values_skip_arg["skip_host_key"])

            self.server_test_1.skip_host_key = False
            values_with_key = self.server_test_1._get_ssh_connection_values()
            self.assertEqual(values_with_key["host_key"], "test_key")
            self.assertFalse(values_with_key["skip_host_key"])
            create_conn.assert_not_called()

    def test_mask_command_result_general_secret(self):
        """General secret substring is not left in the returned response."""
        placeholder = self.Key.SECRET_VALUE_PLACEHOLDER
        log = self.CommandLog.create(
            {
                "server_id": self.server_test_1.id,
                "command_id": self.command_create_dir.id,
                "code": f"echo #!cxtower.secret.{self.secret_2.reference}!#",
                "start_date": Datetime.now(),
            }
        )
        result = self.server_test_1._mask_command_result(
            log, 0, ["output secret top leaked"], None
        )
        self.assertNotIn("secret top", result["response"])
        self.assertIn(placeholder, result["response"])

        result_str = self.server_test_1._mask_command_result(
            log, 0, "output secret top leaked", None
        )
        self.assertNotIn("secret top", result_str["response"])
        self.assertIn(placeholder, result_str["response"])

    def test_mask_command_result_scoped_secrets(self):
        """Server and partner+server values are masked; general is not used."""
        placeholder = self.Key.SECRET_VALUE_PLACEHOLDER
        partner = self.env["res.partner"].create({"name": "Mask Partner"})
        partner_server = self.Server.create(
            {
                "name": "Mask Partner Server",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "host_key": "test_key",
                "os_id": self.os_debian_10.id,
                "partner_id": partner.id,
            }
        )
        key = self.Key.create(
            {
                "name": "Scoped Mask Secret",
                "key_type": "s",
                "secret_value": "general-secret-value",
            }
        )
        self.KeyValue.create(
            {
                "key_id": key.id,
                "server_id": partner_server.id,
                "secret_value": "server-secret-value",
            }
        )
        self.KeyValue.create(
            {
                "key_id": key.id,
                "server_id": partner_server.id,
                "partner_id": partner.id,
                "secret_value": "partner-server-secret",
            }
        )
        code = f"echo #!cxtower.secret.{key.reference}!#"

        server_only = self.Server.create(
            {
                "name": "Mask Server Only",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "host_key": "test_key",
                "os_id": self.os_debian_10.id,
            }
        )
        log_server = self.CommandLog.create(
            {
                "server_id": server_only.id,
                "command_id": self.command_create_dir.id,
                "code": code,
                "start_date": Datetime.now(),
            }
        )
        # Attach server-specific value to the new server
        self.KeyValue.create(
            {
                "key_id": key.id,
                "server_id": server_only.id,
                "secret_value": "server-only-secret",
            }
        )
        result_server = server_only._mask_command_result(
            log_server,
            0,
            ["general-secret-value server-only-secret partner-server-secret"],
            None,
        )
        self.assertNotIn("server-only-secret", result_server["response"])
        self.assertIn("general-secret-value", result_server["response"])
        self.assertIn("partner-server-secret", result_server["response"])
        self.assertIn(placeholder, result_server["response"])

        log_partner = self.CommandLog.create(
            {
                "server_id": partner_server.id,
                "command_id": self.command_create_dir.id,
                "code": code,
                "start_date": Datetime.now(),
            }
        )
        result_partner = partner_server._mask_command_result(
            log_partner,
            0,
            ["general-secret-value server-secret-value partner-server-secret"],
            None,
        )
        self.assertNotIn("partner-server-secret", result_partner["response"])
        self.assertIn("general-secret-value", result_partner["response"])
        self.assertIn("server-secret-value", result_partner["response"])
        self.assertIn(placeholder, result_partner["response"])

    def test_finish_twice_one_command_finished(self):
        """Second finish() is a no-op; a two-line plan does not skip a line."""
        log = self.CommandLog.create(
            {
                "server_id": self.server_test_1.id,
                "command_id": self.command_create_dir.id,
                "start_date": Datetime.now(),
            }
        )
        calls = []
        original_finished = type(log)._command_finished

        def _tracking_finished(command_log):
            calls.append(command_log.id)
            return original_finished(command_log)

        with patch.object(type(log), "_command_finished", _tracking_finished):
            log.finish(status=0)
            log.invalidate_recordset()
            log.finish(status=0)
        self.assertEqual(len(calls), 1)

        plan = self.Plan.create({"name": "Two line defer plan"})
        self.plan_line.create(
            {
                "sequence": 10,
                "plan_id": plan.id,
                "command_id": self.command_create_dir.id,
            }
        )
        self.plan_line.create(
            {
                "sequence": 20,
                "plan_id": plan.id,
                "command_id": self.command_list_dir.id,
            }
        )
        with self._patch_defer_handlers([(10, self._defer_ssh)]):
            plan._run_single(self.server_test_1)
        plan_log = self.PlanLog.search(
            [("plan_id", "=", plan.id)], order="id desc", limit=1
        )
        first_log = plan_log.command_log_ids.filtered("is_running")
        self.assertEqual(len(first_log), 1)
        first_log.finish(status=0)
        first_log.finish(status=0)
        plan_log.invalidate_recordset(["command_log_ids"])
        self.assertEqual(len(plan_log.command_log_ids), 2)

    @mute_logger("odoo.addons.cetmix_tower_server.models.cx_tower_command_log")
    def test_finish_lock_skip_does_not_raise(self):
        """LockNotAvailable and SerializationFailure skip the row."""
        log = self.CommandLog.create(
            {
                "server_id": self.server_test_1.id,
                "command_id": self.command_create_dir.id,
                "start_date": Datetime.now(),
            }
        )
        original_execute = self.env.cr.execute

        def raise_lock(query, params=None, *args, **kwargs):
            query_str = query if isinstance(query, str) else str(query)
            if "FOR UPDATE NOWAIT" in query_str:
                raise LockNotAvailable()
            return original_execute(query, params, *args, **kwargs)

        with patch.object(self.env.cr, "execute", side_effect=raise_lock):
            log.finish(status=0)
        log.invalidate_recordset()
        self.assertTrue(log.is_running)

        def raise_serialization(query, params=None, *args, **kwargs):
            query_str = query if isinstance(query, str) else str(query)
            if "FOR UPDATE NOWAIT" in query_str:
                raise SerializationFailure()
            return original_execute(query, params, *args, **kwargs)

        with patch.object(self.env.cr, "execute", side_effect=raise_serialization):
            log.finish(status=0)
        log.invalidate_recordset()
        self.assertTrue(log.is_running)

    def test_server_status_applied_on_successful_finish_only(self):
        """server_status is set on successful finish, not timeout/stop/running."""
        command = self.Command.create(
            {
                "name": "Status command",
                "action": "ssh_command",
                "code": "ls",
                "server_status": "stopping",
            }
        )
        original_status = self.server_test_1.status
        running_log = self.CommandLog.create(
            {
                "server_id": self.server_test_1.id,
                "command_id": command.id,
                "start_date": Datetime.now(),
            }
        )
        self.assertEqual(self.server_test_1.status, original_status)

        running_log.finish(status=0)
        self.assertEqual(self.server_test_1.status, "stopping")

        self.server_test_1.status = original_status
        timeout_log = self.CommandLog.create(
            {
                "server_id": self.server_test_1.id,
                "command_id": command.id,
                "start_date": Datetime.now(),
            }
        )
        timeout_log.finish(status=COMMAND_TIMED_OUT)
        self.assertEqual(self.server_test_1.status, original_status)

        stop_log = self.CommandLog.create(
            {
                "server_id": self.server_test_1.id,
                "command_id": command.id,
                "start_date": Datetime.now(),
            }
        )
        stop_log.finish(status=COMMAND_STOPPED)
        self.assertEqual(self.server_test_1.status, original_status)

    def test_command_runner_does_not_apply_server_status_with_log(self):
        """Waypoint-style {status: 0} with a log does not write server_status."""
        command = self.Command.create(
            {
                "name": "Waypoint style status",
                "action": "ssh_command",
                "code": "ls",
                "server_status": "stopping",
            }
        )
        log = self.CommandLog.create(
            {
                "server_id": self.server_test_1.id,
                "command_id": command.id,
                "start_date": Datetime.now(),
            }
        )
        original_status = self.server_test_1.status
        with patch.object(
            self.registry["cx.tower.server"],
            "_command_runner_ssh",
            return_value={"status": 0, "response": "ok", "error": None},
        ):
            self.server_test_1._command_runner(
                command=command,
                log_record=log,
                rendered_command_code="ls",
            )
        self.assertEqual(self.server_test_1.status, original_status)
        self.assertTrue(log.is_running)

    def test_zombie_domain_hook_excludes_logs(self):
        """An extra false predicate leaves matching logs running."""
        ssh_command = self.Command.create(
            {
                "name": "Zombie hook SSH",
                "code": "ls -la",
                "action": "ssh_command",
            }
        )
        self.env["ir.config_parameter"].sudo().set_param(
            "cetmix_tower_server.command_timeout", "10"
        )
        old_time = Datetime.now() - timedelta(seconds=20)
        zombie_log = self.CommandLog.create(
            {
                "command_id": ssh_command.id,
                "server_id": self.server_test_1.id,
                "start_date": old_time,
            }
        )
        with patch.object(
            self.registry["cx.tower.server"],
            "_get_zombie_command_log_domain",
            return_value=[("id", "=", 0)],
        ):
            self.server_test_1._check_zombie_commands()
        zombie_log.invalidate_recordset()
        self.assertTrue(zombie_log.is_running)
