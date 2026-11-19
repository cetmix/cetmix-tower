# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from unittest import TestCase
from unittest.mock import patch

import yaml
from psycopg2 import errors

from odoo import SUPERUSER_ID, _, api, fields, sql_db
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

from odoo.addons.cetmix_tower_server.tests.common_jets import TestTowerJetsCommon


class BackupCommon(TestTowerJetsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.startClassPatcher(
            patch.object(
                type(cls.Server), "_get_command_defer_handlers", return_value=[]
            )
        )
        cls.Backup = cls.env["cx.tower.backup"]
        cls.BackupTemplate = cls.env["cx.tower.backup.template"]
        cls.server_test_1.manager_ids |= cls.manager
        cls.template = cls.JetTemplate.create(
            {
                "name": "Backup test template",
                "manager_ids": [(4, cls.manager.id)],
            }
        )
        cls.source = cls.Jet.create(
            {
                "name": "Backup source",
                "jet_template_id": cls.template.id,
                "server_id": cls.server_test_1.id,
                "manager_ids": [(4, cls.manager.id)],
            }
        )
        cls.backup_plan = cls._make_plan(
            "Backup", "backup.update_metadata({'location': 'test://object'})"
        )
        cls.restore_plan = cls._make_plan("Restore", "result = {'exit_code': 0}")
        cls.delete_plan = cls._make_plan("Delete", "result = {'exit_code': 0}")
        cls.backup_template = cls.BackupTemplate.create(
            {
                "name": "Backup test",
                "jet_template_id": cls.template.id,
                "plan_backup_id": cls.backup_plan.id,
                "plan_restore_id": cls.restore_plan.id,
            }
        )

    @classmethod
    def _make_plan(cls, name, code, access_level="3"):
        command = cls.Command.create(
            {
                "name": name,
                "action": "python_code",
                "code": code,
                "access_level": access_level,
            }
        )
        return cls.Plan.create(
            {
                "name": name,
                "access_level": access_level,
                "line_ids": [(0, 0, {"command_id": command.id})],
            }
        )

    def _defer(self):
        return patch.object(
            type(self.server_test_1),
            "_get_command_defer_handlers",
            return_value=[(1, lambda *args, **kwargs: True)],
        )

    def _backup(self, **values):
        return self.Backup.create(
            {
                "name": "Stored backup",
                "backup_template_id": self.backup_template.id,
                "jet_id": self.source.id,
                "server_id": self.server_test_1.id,
                "state": "done",
                **values,
            }
        )


class TestTowerBackup(BackupCommon):
    def test_yaml_export_and_import_respect_root_fields(self):
        """Allow empty-field exports while keeping imports subject to Root access."""
        command = self.Command.create(
            {
                "name": "Manager export command",
                "action": "ssh_command",
                "code": "echo backup",
                "access_level": "2",
                "manager_ids": [(4, self.manager.id)],
                "backup_template_id": self.backup_template.id,
            }
        )
        manager_command = command.with_user(self.manager)
        with self.assertRaises(AccessError):
            manager_command.read(["backup_template_id"])
        message = 'You must be a member of the "Root" group to export this snippet'
        for operation in (
            manager_command._prepare_record_for_yaml,
            lambda: list(manager_command._iter_yaml_export_dependencies(True)),
        ):
            with self.assertRaises(AccessError) as error:
                operation()
            self.assertEqual(str(error.exception), message)
        with self.assertRaises(AccessError):
            manager_command.read(["backup_template_id"])
        command.backup_template_id = False
        exported = manager_command._prepare_record_for_yaml()
        self.assertNotIn("backup_template_id", exported)
        list(manager_command._iter_yaml_export_dependencies(True))
        command.backup_template_id = self.backup_template
        self.manager.groups_id |= self.env.ref("cetmix_tower_yaml.group_import")
        wizard = (
            self.env["cx.tower.yaml.import.wiz"]
            .with_user(self.manager)
            .create(
                {
                    "if_record_exists": "create",
                    "yaml_code": yaml.safe_dump(
                        {
                            "cetmix_tower_yaml_version": 1,
                            "records": [
                                {
                                    **yaml.safe_load(command.yaml_code),
                                    "access_level": "root",
                                }
                            ],
                        }
                    ),
                }
            )
        )
        with self.assertRaises(AccessError) as error:
            wizard.action_import_yaml()
        self.assertEqual(
            str(error.exception),
            'You must be a member of the "Root" group to import this snippet',
        )
        for value in (False, self.backup_template.reference):
            with self.assertRaises(AccessError):
                manager_command._post_process_yaml_dict_values(
                    {"backup_template_id": value}
                )
        result = wizard.sudo().action_import_yaml()
        imported_command = self.Command.browse(result["res_id"])
        self.assertEqual(imported_command.backup_template_id, self.backup_template)
        self.manager.groups_id -= self.env.ref("cetmix_tower_yaml.group_import")
        with self.assertRaises(AccessError):
            wizard.action_import_yaml()
        imported = command._post_process_yaml_dict_values(
            {"backup_template_id": self.backup_template.reference}
        )
        self.assertEqual(imported["backup_template_id"], self.backup_template.id)
        self.assertEqual(
            command._prepare_record_for_yaml()["backup_template_id"],
            self.backup_template.reference,
        )

    def test_manager_exports_empty_backup_fields_on_all_extended_models(self):
        """Empty backup relations must not prevent ordinary Manager exports."""
        command = self.Command.create(
            {
                "name": "Ordinary export command",
                "access_level": "2",
                "manager_ids": [(4, self.manager.id)],
            }
        )
        template = self.JetTemplate.create(
            {"name": "Ordinary export template", "manager_ids": [(4, self.manager.id)]}
        )
        waypoint = self.env["cx.tower.jet.waypoint.template"].create(
            {"name": "Ordinary waypoint", "jet_template_id": template.id}
        )
        task = self.env["cx.tower.scheduled.task"].create(
            {
                "name": "Ordinary task",
                "action": "command",
                "command_id": command.id,
                "manager_ids": [(4, self.manager.id)],
            }
        )
        for record, field in (
            (command, "backup_template_id"),
            (template, "backup_template_ids"),
            (waypoint, "backup_template_id"),
            (task, "backup_template_id"),
        ):
            with self.subTest(model=record._name):
                manager_record = record.with_user(self.manager)
                exported = manager_record._prepare_record_for_yaml()
                self.assertEqual(exported["name"], record.name)
                self.assertNotIn(field, exported)
                list(manager_record._iter_yaml_export_dependencies(True))

    def test_backup_template_cannot_move_existing_backups(self):
        self._backup()
        other = self.JetTemplate.create({"name": "Other backup owner"})
        self.backup_template.write({"jet_template_id": self.template.id})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.backup_template.jet_template_id = other
        self.assertEqual(self.backup_template.jet_template_id, self.template)

    def test_restore_destination_cannot_be_deleted_while_running(self):
        backup = self._backup()
        with self._defer():
            destination = backup.restore(self.server_test_1)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            destination.unlink()
        self.assertTrue(destination.exists())
        backup.plan_log_ids.finish(0)
        destination.unlink()

    def test_running_backup_protects_unstarted_child_plan(self):
        child = self._make_plan("Backup child", "result = {'exit_code': 0}")
        command = self.Command.create(
            {
                "name": "Run backup child",
                "action": "plan",
                "access_level": "3",
                "flight_plan_id": child.id,
            }
        )
        self.backup_plan.write({"line_ids": [(0, 0, {"command_id": command.id})]})
        with self._defer():
            backup = self.source.create_backup(self.backup_template)
        self.assertFalse(self.PlanLog.search_count([("plan_id", "=", child.id)]))
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            child.unlink()
        self.assertEqual(command.flight_plan_id, child)
        backup.plan_log_ids.finish(0)
        child.unlink()

    def test_failed_backup_start_leaves_waypoint_retryable(self):
        template = self.env["cx.tower.jet.waypoint.template"].create(
            {
                "name": "Retryable backup waypoint",
                "jet_template_id": self.template.id,
                "backup_template_id": self.backup_template.id,
            }
        )
        waypoint = self.env["cx.tower.jet.waypoint"].create(
            {
                "name": "Retry waypoint",
                "jet_id": self.source.id,
                "waypoint_template_id": template.id,
            }
        )
        other = self.JetTemplate.create({"name": "Wrong backup owner"})
        self.backup_template.jet_template_id = other
        # Emulate the command runner catching the error without a rollback.
        with TestCase.assertRaises(self, ValidationError):
            waypoint.prepare(is_destination=True)
        self.assertEqual(waypoint.state, "draft")
        self.assertFalse(waypoint.is_destination)
        self.assertFalse(waypoint.backup_id)
        self.backup_template.jet_template_id = self.template
        waypoint.prepare()
        self.assertEqual(waypoint.state, "ready")

    def test_scheduled_task_reports_synchronous_backup_failure(self):
        self.backup_plan.line_ids.command_id.code = "result = {'exit_code': 1}"
        task = self.env["cx.tower.scheduled.task"].create(
            {
                "name": "Failing backup task",
                "action": "backup",
                "backup_template_id": self.backup_template.id,
                "jet_ids": [(4, self.source.id)],
            }
        )
        errors = task._run_action()
        self.assertEqual(len(errors), 1)
        self.assertEqual(
            self.Backup.search([("jet_id", "=", self.source.id)]).state, "failed"
        )

    def test_command_result_reports_synchronous_backup_failure(self):
        self.backup_plan.line_ids.command_id.code = "result = {'exit_code': 1}"
        command = self.Command.create(
            {
                "name": "Failing backup command",
                "action": "create_backup",
                "backup_template_id": self.backup_template.id,
            }
        )
        result = self.source.run_command(command)
        self.assertEqual(result["status"], -510)
        log = self.CommandLog.search(
            [("command_id", "=", command.id)], order="id desc", limit=1
        )
        self.assertEqual(log.command_status, -510)
        self.assertEqual(
            self.Backup.browse(result["response"]["backup_id"]).state, "failed"
        )

    def test_failed_restore_wizard_opens_log_and_keeps_destination(self):
        self.restore_plan.line_ids.command_id.code = "result = {'exit_code': 1}"
        backup = self._backup()
        wizard = self.env["cx.tower.backup.restore.wizard"].create(
            {"backup_id": backup.id, "server_id": self.server_test_1.id}
        )
        action = wizard.action_confirm()
        self.assertEqual(action["res_model"], "cx.tower.plan.log")
        log = self.PlanLog.browse(action["res_id"])
        self.assertEqual(log.backup_id, backup)
        self.assertEqual(log.plan_status, 1)
        self.assertTrue(log.jet_id.exists())
        self.assertNotEqual(log.jet_id, self.source)
        self.assertEqual(backup.state, "done")

    def test_yaml_presence_probe_does_not_cache_sibling_root_values(self):
        commands = self.Command.create(
            [
                {
                    "name": "Empty backup field",
                    "access_level": "2",
                    "manager_ids": [(4, self.manager.id)],
                },
                {
                    "name": "Populated backup field",
                    "access_level": "2",
                    "manager_ids": [(4, self.manager.id)],
                    "backup_template_id": self.backup_template.id,
                },
            ]
        )
        commands.flush_recordset()
        commands.invalidate_recordset()
        manager_commands = commands.with_user(self.manager).with_prefetch(commands.ids)
        empty, populated = manager_commands
        self.assertEqual(set(empty._prefetch_ids), set(commands.ids))
        empty._get_yaml_export_field_names()
        # Odoo's assertRaises(AccessError) clears the cache and would hide a leak.
        with TestCase.assertRaises(self, AccessError):
            self.assertFalse(populated.backup_template_id)

    def test_backup_size_persists_fractional_mb(self):
        """Persist command-supplied MB without integer limits or forced rounding."""
        backup = self._backup()
        self.assertEqual(backup.backup_size, 0.0)
        self.assertNotIn("backup_size_mb", backup._fields)
        for size_mb in (1 / 1048576, 0.5, 1.25, 2048.25, 2147483648.5, 0.0):
            with self.subTest(size_mb=size_mb), self.env.cr.savepoint():
                backup.write({"backup_size": size_mb})
                backup.flush_recordset(["backup_size"])
                backup.invalidate_recordset(["backup_size"])
                self.assertEqual(backup.backup_size, size_mb)
                self.assertEqual(
                    backup.read(["backup_size"])[0]["backup_size"], size_mb
                )
        self.env.cr.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = %s "
            "AND column_name IN ('backup_size', 'backup_size_mb')",
            [backup._table],
        )
        self.assertEqual(
            dict(self.env.cr.fetchall()), {"backup_size": "double precision"}
        )

    def test_backup_size_is_set_by_tower_command(self):
        """The Backup plan supplies the measured size and the backup URL."""
        self.backup_plan.line_ids.command_id.code = (
            "backup.write({'backup_size': 2048.25, "
            "'url': 'https://storage.example/backup.zip'})\n"
            "result = {'exit_code': 0}"
        )
        backup = self.source.create_backup(self.backup_template)
        self.assertEqual(backup.state, "done")
        self.assertEqual(backup.backup_size, 2048.25)
        backup.invalidate_recordset(["url"])
        self.assertEqual(backup.url, "https://storage.example/backup.zip")

    def test_busy_action_returns_status_and_finishes_calling_command(self):
        """Expected busy admission must not abandon a jet_action command log."""
        with self._defer():
            backup = self.source.create_backup(self.backup_template)
        result = self.source._trigger_action(
            self.action_create, raise_if_not_available=False
        )
        self.assertEqual(result["status"], -505)
        command = self.Command.create(
            {
                "name": "Busy Jet action",
                "action": "jet_action",
                "jet_action_id": self.action_create.id,
                "jet_template_id": self.template.id,
            }
        )
        result = self.source.run_command(command)
        self.assertNotEqual(result["status"], 0)
        log = self.CommandLog.search(
            [("command_id", "=", command.id)], order="id desc", limit=1
        )
        self.assertFalse(log.is_running)
        self.assertNotEqual(log.command_status, 0)
        self.assertEqual(backup.state, "running")

    def test_nonraising_action_recovers_transaction_conflicts(self):
        """Real PostgreSQL errors are contained before they can retry prior work."""
        for code in ("55P03", "40001"):

            def conflict(jet, error_code=code):
                jet.env.cr.execute(
                    "DO $$ BEGIN RAISE EXCEPTION 'busy' USING ERRCODE = %s; END $$",
                    [error_code],
                )

            with (
                self.subTest(code=code),
                self.env.cr.savepoint(),
                mute_logger("odoo.sql_db"),
                patch.object(type(self.source), "_lock_backup_operation", conflict),
            ):
                result = self.source._trigger_action(
                    self.action_create, raise_if_not_available=False
                )
                self.assertEqual(result["status"], -505)
                self.env.cr.execute("SELECT 1")
                self.assertEqual(self.env.cr.fetchone(), (1,))

    def test_cleanup_skips_conflicted_backup_and_continues(self):
        """Each failed upload is independent and remains retryable after contention."""
        self.backup_template.plan_delete_id = self.delete_plan
        original = type(self.Backup)._start_delete
        for code in ("55P03", "40001"):
            first = self._backup(state="failed")
            second = self._backup(state="failed")

            def conflict(backup, *args, backup_id=first.id, error_code=code, **kwargs):
                if backup.id == backup_id:
                    backup.env.cr.execute(
                        "DO $$ BEGIN RAISE EXCEPTION 'busy' USING ERRCODE = %s; END $$",
                        [error_code],
                    )
                return original(backup, *args, **kwargs)

            with (
                self.subTest(code=code),
                self.env.cr.savepoint(),
                mute_logger("odoo.sql_db"),
                patch.object(type(self.Backup), "_start_delete", conflict),
            ):
                self.Backup._run_cleanup()
            self.assertTrue(first.exists())
            self.assertEqual(first.state, "failed")
            self.assertFalse(second.exists())
            self.env.cr.execute("SELECT 1")
            self.assertEqual(self.env.cr.fetchone(), (1,))
            self.Backup._run_cleanup()
            self.assertFalse(first.exists())

    def test_interactive_delete_reports_busy_jet(self):
        """The Delete button reports a busy Jet without changing the backup."""
        self.backup_template.plan_delete_id = self.delete_plan
        backup = self._backup()
        self.source.target_state_id = self.state_running
        with self.assertRaisesRegex(ValidationError, "Jet is busy"):
            backup.action_delete()
        self.assertEqual(backup.state, "done")
        backup.unlink()
        self.assertTrue(backup.exists())
        self.source.target_state_id = False
        backup.action_delete()
        self.assertFalse(backup.exists())

    def test_busy_jet_keeps_waypoint_ready_for_delete_retry(self):
        """Admission must succeed before a linked waypoint enters Deleting."""
        self.backup_template.plan_delete_id = self.delete_plan
        backup = self._backup()
        template = self.env["cx.tower.jet.waypoint.template"].create(
            {
                "name": "Busy delete waypoint",
                "jet_template_id": self.template.id,
                "backup_template_id": self.backup_template.id,
            }
        )
        waypoint = self.env["cx.tower.jet.waypoint"].create(
            {
                "name": "Busy delete",
                "jet_id": self.source.id,
                "waypoint_template_id": template.id,
                "backup_id": backup.id,
                "state": "ready",
            }
        )
        self.source.target_state_id = self.state_running
        with self.assertRaises(ValidationError):
            waypoint.unlink()
        self.assertEqual(waypoint.state, "ready")
        self.assertEqual(backup.state, "done")
        with mute_logger(
            "odoo.addons.cetmix_tower_backup.models.cx_tower_jet_waypoint"
        ):
            waypoint.with_context(waypoint_no_raise_on_delete=True).unlink()
        self.assertEqual(waypoint.state, "ready")
        self.source.target_state_id = False
        waypoint.unlink()
        self.assertFalse(waypoint.exists())
        self.assertFalse(backup.exists())

    def test_capture_and_python_context(self):
        variable = self.Variable.create(
            {"name": "Backup own value", "reference": "backup_own_value"}
        )
        self.source.set_variable_value(variable.reference, "saved")
        backup = self.source.create_backup(
            self.backup_template, variable_values={"bucket": "test"}
        )
        self.assertEqual(backup.state, "done")
        self.assertEqual(backup.variable_values, {variable.reference: "saved"})
        self.assertEqual(backup.custom_variable_values, {"bucket": "test"})
        self.assertEqual(backup.metadata, {"location": "test://object"})
        self.assertFalse(backup.operation_token)
        self.assertTrue(backup.plan_log_ids.has_backup_values)
        self.assertTrue(
            all(backup.plan_log_ids.command_log_ids.mapped("has_backup_values"))
        )
        self.assertFalse(self.Command._get_python_command_eval_context()["backup"])

    def test_deferred_result_and_forged_token(self):
        with self._defer():
            backup = self.source.create_backup(self.backup_template)
        log = backup.plan_log_ids
        self.assertEqual(backup.state, "running")
        forged = self.PlanLog.create(
            {
                "server_id": self.server_test_1.id,
                "plan_id": self.backup_plan.id,
                "backup_id": backup.id,
                "backup_operation": "backup",
            }
        )
        with mute_logger("odoo.addons.cetmix_tower_backup.models.cx_tower_backup"):
            forged.finish(0)
        self.assertEqual(backup.state, "running")
        log.finish(0)
        self.assertEqual(backup.state, "done")
        with mute_logger("odoo.addons.cetmix_tower_backup.models.cx_tower_backup"):
            log.finish(-1)
        self.assertEqual(backup.state, "done")

    def test_failed_backup_finalizes_when_parent_completion_hook_raises(self):
        """Notifications must not leave a failed plan's backup reserving its Jet."""
        from odoo.addons.cetmix_tower_server.models.cx_tower_plan_log import (
            CxTowerPlanLog as CorePlanLog,
        )

        with self._defer():
            backup = self.source.create_backup(self.backup_template)
        with (
            patch.object(
                CorePlanLog,
                "_plan_finished",
                side_effect=ValidationError("notification failed"),
            ),
            mute_logger(
                "odoo.addons.cetmix_tower_server.models.cx_tower_plan_log",
                "odoo.addons.cetmix_tower_backup.models.cx_tower_plan_log",
            ),
        ):
            backup.plan_log_ids.command_log_ids.finish(status=601)
        self.assertFalse(backup.plan_log_ids.is_running)
        self.assertEqual(backup.plan_log_ids.plan_status, 601)
        self.assertEqual(backup.state, "failed")
        self.assertFalse(backup.operation_token)
        self.assertFalse(self.source.active_backup_id)

    def test_terminal_result_survives_sql_error_in_parent_hook(self):
        from odoo.addons.cetmix_tower_server.models.cx_tower_plan_log import (
            CxTowerPlanLog as CorePlanLog,
        )

        def fail_notification(log):
            log.env.cr.execute("SELECT 1 / 0")

        with self._defer():
            backup = self.source.create_backup(self.backup_template)
        with (
            patch.object(CorePlanLog, "_plan_finished", fail_notification),
            mute_logger(
                "odoo.sql_db",
                "odoo.addons.cetmix_tower_backup.models.cx_tower_plan_log",
            ),
        ):
            backup.plan_log_ids.command_log_ids.finish(status=601)
        self.assertEqual(backup.state, "failed")
        self.assertFalse(self.source.active_backup_id)
        self.env.cr.execute("SELECT 1")
        self.assertEqual(self.env.cr.fetchone(), (1,))

    def _record_terminal_backup_log(self, backup, status):
        """Build a finished execution whose backup callback was missed.

        Args:
            backup (cx.tower.backup): Operation with one deferred plan log.
            status (int): Recorded command and plan exit status.

        Returns:
            None: Marks the command and plan finished without invoking callbacks.
        """
        log = backup.plan_log_ids
        finished = fields.Datetime.now()
        log.command_log_ids.write({"finish_date": finished, "command_status": status})
        log.write({"finish_date": finished, "plan_status": status})

    def test_reconcile_recovers_missed_results_and_preserves_newer_claims(self):
        for status, expected in ((601, "failed"), (0, "done")):
            with self._defer():
                backup = self.source.create_backup(self.backup_template)
            self._record_terminal_backup_log(backup, status)
            self.PlanLog._reconcile_backup_operations()
            self.assertEqual(backup.state, expected)
            self.assertFalse(backup.operation_token)
            self.assertFalse(self.source.active_backup_id)
            self.PlanLog._reconcile_backup_operations()
            self.assertEqual(backup.state, expected)
        with self._defer():
            old = self.source.create_backup(self.backup_template)
        newer = self._backup(state="running")
        self.source.active_backup_id = newer
        self._record_terminal_backup_log(old, 601)
        self.PlanLog._reconcile_backup_operations()
        self.assertEqual(old.state, "failed")
        self.assertEqual(self.source.active_backup_id, newer)

    def test_reconcile_ignores_running_plans_and_obsolete_tokens(self):
        with self._defer():
            backup = self.source.create_backup(self.backup_template)
        self.PlanLog.create(
            {
                "server_id": self.server_test_1.id,
                "plan_id": self.backup_plan.id,
                "backup_id": backup.id,
                "backup_operation": "backup",
                "backup_token": backup.operation_token,
                "parent_flight_plan_log_id": backup.plan_log_ids.id,
                "start_date": fields.Datetime.now(),
                "finish_date": fields.Datetime.now(),
                "plan_status": 601,
            }
        )
        self.PlanLog._reconcile_backup_operations()
        self.assertEqual(backup.state, "running")
        backup.operation_token = "newer-operation"
        self._record_terminal_backup_log(backup, 601)
        self.PlanLog._reconcile_backup_operations()
        self.assertEqual(backup.state, "running")
        self.assertEqual(self.source.active_backup_id, backup)

    def test_finish_fallback_applies_result_when_hook_is_skipped(self):
        with self._defer():
            backup = self.source.create_backup(self.backup_template)
        with patch.object(type(self.PlanLog), "_plan_finished", return_value=True):
            backup.plan_log_ids.command_log_ids.finish(status=601)
        self.assertEqual(backup.state, "failed")
        self.assertFalse(self.source.active_backup_id)

    def test_reconcile_recovers_terminal_delete_results(self):
        self.backup_template.plan_delete_id = self.delete_plan
        for status in (601, 0):
            backup = self._backup()
            with self._defer():
                backup.unlink()
            self._record_terminal_backup_log(backup, status)
            self.PlanLog._reconcile_backup_operations()
            if status:
                self.assertEqual(backup.state, "delete_failed")
            else:
                self.assertFalse(backup.exists())
            self.assertFalse(self.source.active_backup_id)

    def test_reconcile_isolates_one_failed_recovery(self):
        other = self.Jet.create(
            {
                "name": "Other recovery Jet",
                "jet_template_id": self.template.id,
                "server_id": self.server_test_1.id,
            }
        )
        with self._defer():
            first = self.source.create_backup(self.backup_template)
            second = other.create_backup(self.backup_template)
        self._record_terminal_backup_log(first, 601)
        self._record_terminal_backup_log(second, 601)
        failed_log_id = first.plan_log_ids.id
        original = type(self.PlanLog)._finalize_backup_result

        def recover(log):
            if log.id == failed_log_id:
                log.env.cr.execute("SELECT 1 / 0")
            return original(log)

        with (
            patch.object(type(self.PlanLog), "_finalize_backup_result", recover),
            mute_logger(
                "odoo.sql_db",
                "odoo.addons.cetmix_tower_backup.models.cx_tower_plan_log",
            ),
        ):
            self.PlanLog._reconcile_backup_operations()
        self.assertEqual(first.state, "running")
        self.assertEqual(second.state, "failed")
        self.assertFalse(other.active_backup_id)
        self.env.cr.execute("SELECT 1")
        self.assertEqual(self.env.cr.fetchone(), (1,))
        self.PlanLog._reconcile_backup_operations()
        self.assertEqual(first.state, "failed")
        self.assertFalse(self.source.active_backup_id)

    def test_failed_and_stopped_backup(self):
        for status in (-1, -308):
            with self._defer():
                backup = self.source.create_backup(self.backup_template)
            backup.plan_log_ids.command_log_ids.finish(status=status)
            self.assertEqual(backup.state, "failed")
            self.assertFalse(self.source.active_backup_id)
            with self.assertRaises(ValidationError):
                backup.restore(self.server_test_1, state=self.state_running)

    def test_template_busy_and_trigger_guards(self):
        other = self.BackupTemplate.create(
            {
                "name": "Other",
                "jet_template_id": self.jet_template_test.id,
                "plan_backup_id": self.backup_plan.id,
                "plan_restore_id": self.restore_plan.id,
            }
        )
        with self.assertRaises(ValidationError):
            self.source.create_backup(other)
        with self.assertRaises(ValidationError):
            self.source.create_backup("unknown_backup_template")
        self.source.target_state_id = self.state_running
        with self.assertRaises(ValidationError):
            self.source.create_backup(self.backup_template)
        with self.assertRaises(ValidationError):
            self.source.create_backup(self.backup_template, ignore_busy=True)
        with self.assertRaises(ValidationError):
            self.source.create_backup(self.backup_template, waypoint=self.waypoint)

    def test_backup_claim_blocks_new_actions_and_other_backups(self):
        """An active backup reserves the Jet even without a lifecycle transition."""
        with self._defer():
            backup = self.source.create_backup(self.backup_template)
        self.assertEqual(self.source.active_backup_id, backup)
        self.assertTrue(self.source._is_busy())
        for operation in (
            lambda: self.source.create_backup(self.backup_template),
            lambda: self.source.create_backup(self.backup_template, ignore_busy=True),
            lambda: self.source._trigger_action(self.action_create),
            lambda: self.source.bring_to_state(self.state_running.reference),
        ):
            with self.assertRaises(ValidationError):
                operation()
        backup.plan_log_ids.command_log_ids.finish(status=-1)
        self.assertFalse(self.source.active_backup_id)
        self.assertFalse(self.source._is_busy())
        self.assertEqual(self.source.create_backup(self.backup_template).state, "done")

    def test_standalone_backup_command_cannot_bypass_another_backup(self):
        """Empty action links never establish ownership of a backup claim."""
        command = self.Command.create(
            {
                "name": "Independent backup request",
                "action": "create_backup",
                "backup_template_id": self.backup_template.id,
            }
        )
        caller = self.Plan.create(
            {
                "name": "Independent backup plan",
                "line_ids": [(0, 0, {"command_id": command.id})],
            }
        )
        with self._defer():
            backup = self.source.create_backup(self.backup_template)
        log = self.source.run_flight_plan(caller)
        self.assertEqual(log.plan_status, -510)
        self.assertEqual(self.source.active_backup_id, backup)
        self.assertEqual(self.Backup.search_count([("jet_id", "=", self.source.id)]), 1)

    def test_action_owned_backup_and_lifecycle_continuations(self):
        """A current action may await its own backup, then continue its state path."""
        command = self.Command.create(
            {
                "name": "Action-owned backup request",
                "action": "create_backup",
                "backup_template_id": self.backup_template.id,
            }
        )
        child = self.Plan.create(
            {
                "name": "Action-owned backup child",
                "line_ids": [(0, 0, {"command_id": command.id})],
            }
        )
        wrapper = self.Command.create(
            {
                "name": "Run action-owned backup child",
                "action": "plan",
                "flight_plan_id": child.id,
            }
        )
        plan = self.Plan.create(
            {
                "name": "Action-owned backup root",
                "line_ids": [(0, 0, {"command_id": wrapper.id})],
            }
        )
        for name, state_from, state_to, action_plan in (
            ("Prepare", False, self.state_initial, plan),
            ("Build", self.state_initial, self.state_stopped, self.restore_plan),
            ("Start", self.state_stopped, self.state_running, self.restore_plan),
        ):
            self.JetAction.create(
                {
                    "name": name,
                    "jet_template_id": self.template.id,
                    "state_from_id": state_from and state_from.id,
                    "state_to_id": state_to.id,
                    "state_transit_id": self.state_starting.id,
                    "plan_id": action_plan.id,
                }
            )
        self.source.with_user(self.root).bring_to_state(self.state_running.reference)
        self.assertEqual(self.source.state_id, self.state_running)
        self.assertFalse(self.source.current_action_id)
        self.assertFalse(self.source.target_state_id)
        self.assertFalse(self.source.active_backup_id)
        backup = self.Backup.search([("jet_id", "=", self.source.id)])
        self.assertEqual(backup.state, "done")

    def test_update_action_admits_only_its_own_backup(self):
        """An Update admits its backup while excluding standalone and cron triggers."""
        command = self.Command.create(
            {
                "name": "Update backup",
                "action": "create_backup",
                "backup_template_id": self.backup_template.id,
            }
        )
        plan = self.Plan.create(
            {
                "name": "Update with backup",
                "line_ids": [(0, 0, {"command_id": command.id})],
            }
        )
        action = self.JetAction.create(
            {
                "name": "Update",
                "jet_template_id": self.template.id,
                "state_to_id": self.state_running.id,
                "state_transit_id": self.state_starting.id,
                "plan_id": plan.id,
            }
        )
        with self._defer():
            self.source._trigger_action(action)
        action_log = self.PlanLog.search([("jet_action_id", "=", action.id)])
        self.assertTrue(action_log.is_running)
        standalone_command = self.Command.create(
            {
                "name": "Standalone backup during Update",
                "action": "create_backup",
                "backup_template_id": self.backup_template.id,
            }
        )
        with self.assertRaisesRegex(ValidationError, "currently executing an action"):
            self.source.run_command(standalone_command)
        self.server_test_1.run_command(standalone_command, jet=self.source)
        standalone = self.CommandLog.search(
            [("command_id", "=", standalone_command.id), ("plan_log_id", "=", False)]
        )
        self.assertEqual(standalone.command_status, -510)
        task = self.env["cx.tower.scheduled.task"].create(
            {
                "name": "Scheduled backup during Update",
                "action": "backup",
                "backup_template_id": self.backup_template.id,
                "jet_ids": [(4, self.source.id)],
            }
        )
        with mute_logger(
            "odoo.addons.cetmix_tower_backup.models.cx_tower_scheduled_task"
        ):
            self.assertTrue(task._run_action())
        self.assertFalse(self.Backup.search([("jet_id", "=", self.source.id)]))
        with self._defer():
            result = self.server_test_1._command_runner_create_backup(
                action_log.command_log_ids
            )
        self.assertEqual(result["status"], 0)
        backup = self.Backup.browse(result["response"]["backup_id"])
        self.assertEqual(self.source.active_backup_id, backup)
        with self.assertRaises(ValidationError):
            self.source.create_backup(
                self.backup_template,
                ignore_busy=True,
                created_from_command_log=action_log.command_log_ids,
            )
        self.assertEqual(self.source.active_backup_id, backup)
        backup.plan_log_ids.command_log_ids.finish(status=0)
        self.assertEqual(backup.state, "done")
        self.assertFalse(self.source.active_backup_id)
        self.assertEqual(self.source.state_id, self.state_running)

    def test_old_completion_preserves_newer_backup_claim(self):
        """A delayed result cannot release a different operation's reservation."""
        with self._defer():
            old = self.source.create_backup(self.backup_template)
        newer = self._backup(state="running")
        self.source.active_backup_id = newer
        old.plan_log_ids.command_log_ids.finish(status=0)
        self.assertEqual(old.state, "done")
        self.assertEqual(self.source.active_backup_id, newer)
        self.assertTrue(self.source._is_busy())

    def test_delete_claim_blocks_action_and_releases_on_failure(self):
        """Deletion holds the same durable reservation until its plan finishes."""
        self.backup_template.plan_delete_id = self.delete_plan
        backup = self._backup()
        with self._defer():
            backup.unlink()
        self.assertEqual(self.source.active_backup_id, backup)
        with self.assertRaises(ValidationError):
            self.source._trigger_action(self.action_create)
        backup.plan_log_ids.command_log_ids.finish(status=-1)
        self.assertEqual(backup.state, "delete_failed")
        self.assertFalse(self.source.active_backup_id)

    def test_custom_value_precedence(self):
        backup = self._backup(
            custom_variable_values={"bucket": "old", "__backup": "forged"},
            metadata={"location": "stored", "template": "forged"},
        )
        values = backup._get_custom_variable_values(
            {"bucket": "new", "__backup_location": "forged"}
        )
        self.assertEqual(values["bucket"], "new")
        self.assertEqual(values["__backup_location"], "stored")
        self.assertEqual(values["__backup"], backup.reference)
        self.assertEqual(values["__backup_template"], self.backup_template.reference)

    def test_restore_configuration_and_environment(self):
        variable = self.Variable.create(
            {"name": "Restore value", "reference": "restore_value"}
        )
        backup = self._backup(
            variable_values={
                variable.reference: "snapshot",
                "removed_variable": "ignored",
            },
            environment_id=self.env_prod.id,
            custom_variable_values={"bucket": "old"},
        )
        self.template.write(
            {"env_required": True, "environment_default_id": self.env_dev.id}
        )
        with mute_logger(
            "odoo.addons.cetmix_tower_server.models.cx_tower_jet_template"
        ):
            jet = backup.restore(
                self.server_test_1,
                state=self.state_running,
                variable_values={"bucket": "new"},
                environment=self.env_stage,
            )
        self.assertEqual(jet.environment_id, self.env_stage)
        self.assertEqual(jet.variable_value_ids.value_char, "snapshot")
        log = backup.plan_log_ids
        self.assertEqual(log.variable_values["bucket"], "new")
        self.assertEqual(
            log.variable_values["__requested_jet_state__"], self.state_running.reference
        )
        with mute_logger(
            "odoo.addons.cetmix_tower_server.models.cx_tower_jet_template"
        ):
            second = backup.restore(self.server_test_1)
        self.assertEqual(second.environment_id, self.env_prod)
        backup.environment_id = False
        with mute_logger(
            "odoo.addons.cetmix_tower_server.models.cx_tower_jet_template"
        ):
            third = backup.restore(self.server_test_1)
        self.assertEqual(third.environment_id, self.env_dev)
        self.assertEqual(backup.state, "done")
        with (
            patch.object(
                type(self.template), "_allow_jet_creation", return_value=False
            ),
            self.assertRaises(ValidationError),
        ):
            backup.restore(self.server_test_1)

    def test_bulk_delete_continues_after_each_deferred_plan(self):
        """All selected backups are processed while only one reserves their Jet."""
        self.backup_template.plan_delete_id = self.delete_plan
        backups = self._backup() | self._backup() | self._backup()
        with self._defer():
            backups.unlink()
            for expected_remaining in (3, 2, 1):
                remaining = backups.exists()
                self.assertEqual(len(remaining), expected_remaining)
                deleting = remaining.filtered(lambda backup: backup.state == "deleting")
                self.assertEqual(len(deleting), 1)
                self.assertEqual(self.source.active_backup_id, deleting)
                deleting.plan_log_ids.command_log_ids.finish(status=0)
        self.assertFalse(backups.exists())
        self.assertFalse(self.source.active_backup_id)

    def test_bulk_delete_continues_after_failure_and_blocks_queued_restore(self):
        self.backup_template.plan_delete_id = self.delete_plan
        backups = self._backup() | self._backup()
        with self._defer():
            backups.unlink()
            first = backups.filtered(lambda backup: backup.state == "deleting")
            second = backups - first
            self.assertTrue(second.delete_requested)
            with self.assertRaisesRegex(ValidationError, "queued for deletion"):
                second.restore(self.server_test_1)
            first.plan_log_ids.command_log_ids.finish(status=-1)
            self.assertEqual(first.state, "delete_failed")
            self.assertEqual(second.state, "deleting")
            second.plan_log_ids.command_log_ids.finish(status=0)
        self.assertFalse(second.exists())
        self.Backup._run_cleanup()
        self.assertTrue(first.exists())

    def test_bulk_delete_inline_and_record_only(self):
        self.assertTrue(self.Backup.browse().unlink())
        self.backup_template.plan_delete_id = self.delete_plan
        backups = self.Backup.browse()
        for _index in range(12):
            backups |= self._backup()
        backups.unlink()
        self.assertFalse(backups.exists())
        self.assertFalse(self.source.active_backup_id)
        self.backup_template.plan_delete_id = False
        records = self._backup() | self._backup()
        records.unlink()
        self.assertFalse(records.exists())

    def test_bulk_delete_dispatch_failure_is_durable_and_retryable(self):
        self.backup_template.plan_delete_id = self.delete_plan
        backups = self._backup() | self._backup()
        with patch.object(
            type(self.server_test_1),
            "run_flight_plan",
            side_effect=ValidationError("dispatch failed"),
        ):
            backups.unlink()
        self.assertTrue(all(backups.mapped("delete_requested")))
        self.assertEqual(set(backups.mapped("state")), {"done"})
        self.assertFalse(self.source.active_backup_id)
        self.Backup._run_cleanup()
        self.assertFalse(backups.exists())

    def test_bulk_delete_with_queue_jobs(self):
        if "queue_job_id" not in self.CommandLog._fields:
            self.skipTest("Requires cetmix_tower_server_queue")
        from odoo.addons.queue_job.tests.common import trap_jobs

        self.backup_template.plan_delete_id = self.delete_plan
        backups = self._backup() | self._backup() | self._backup()

        def handlers(server):
            return [(50, server._try_defer_command_queue)]

        with (
            patch.object(
                type(self.server_test_1), "_get_command_defer_handlers", handlers
            ),
            trap_jobs() as trap,
        ):
            backups.unlink()
            self.assertTrue(backups.exists())
            for _index in range(3):
                trap.perform_enqueued_jobs()
            self.assertFalse(trap.enqueued_jobs)
            self.assertFalse(backups.exists())
        self.assertFalse(self.source.active_backup_id)

    def test_delete_success_failure_busy_and_orphan(self):
        self.backup_template.plan_delete_id = self.delete_plan
        backup = self._backup()
        with self._defer():
            backup.unlink()
        self.assertEqual(backup.state, "deleting")
        backup.plan_log_ids.command_log_ids.finish(status=-301)
        self.assertEqual(backup.state, "delete_failed")
        with self.assertRaises(ValidationError):
            backup.restore(self.server_test_1)
        backup.unlink()
        self.assertFalse(backup.exists())
        orphan = self._backup(jet_id=False, server_id=False)
        self.assertTrue(orphan.delete_warning)
        with mute_logger("odoo.addons.cetmix_tower_backup.models.cx_tower_backup"):
            orphan.unlink()
        self.assertFalse(orphan.exists())
        with self._defer():
            log = self.source.run_flight_plan(self.delete_plan)
        waiting = self._backup()
        waiting.unlink()
        self.assertEqual(waiting.state, "done")
        with self.assertRaisesRegex(ValidationError, "Delete plan is already running"):
            waiting.action_delete()
        log.command_log_ids.finish(status=0)
        waiting.unlink()
        self.assertFalse(waiting.exists())

    def test_running_restore_blocks_delete_and_retention(self):
        self.backup_template.keep_last = 1
        old = self._backup(create_date="2026-01-01 00:00:00")
        with self._defer():
            old.restore(self.server_test_1)
        self._backup(create_date="2026-01-02 00:00:00")
        with self.assertRaises(ValidationError):
            old.unlink()
        self.Backup._run_cleanup()
        self.assertTrue(old.exists())
        old.plan_log_ids.finish(0)
        self.Backup._run_cleanup()
        self.assertFalse(old.exists())

    def test_jet_deletion_survival_and_running_guards(self):
        backup = self._backup()
        with self._defer():
            running = self.source.create_backup(self.backup_template)
        with self.assertRaises(ValidationError):
            self.source.unlink()
        with self.assertRaises(ValidationError):
            self.backup_plan.unlink()
        running.plan_log_ids.finish(0)
        self.source.unlink()
        self.assertTrue(backup.exists())
        self.assertFalse(backup.jet_id)
        self.backup_template.plan_delete_id = self.delete_plan
        with self._defer():
            backup.unlink()
        with self.assertRaises(ValidationError):
            self.server_test_1.unlink()
        backup.plan_log_ids.finish(0)
        self.assertFalse(backup.exists())

    def test_root_plan_tree_and_history_guards(self):
        command = self.backup_plan.line_ids.command_id
        for record in (self.backup_plan, command):
            with self.assertRaises(ValidationError), self.env.cr.savepoint():
                record.access_level = "2"
        lower = self.Command.create(
            {"name": "Lower", "action": "python_code", "access_level": "2"}
        )
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env["cx.tower.plan.line"].create(
                {"plan_id": self.backup_plan.id, "command_id": lower.id}
            )
        line = self.env["cx.tower.plan.line"].create(
            {"plan_id": self.plan_1.id, "command_id": lower.id}
        )
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            line.plan_id = self.backup_plan
        backup = self.source.create_backup(self.backup_template)
        self.backup_template.plan_backup_id = self.restore_plan
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.backup_plan.access_level = "2"
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            command.access_level = "2"
        self.source.unlink()
        self.backup_plan.access_level = "2"
        command.access_level = "2"
        self.assertTrue(backup.exists())

    def test_running_detached_plan_still_protects_new_lines(self):
        with self._defer():
            backup = self.source.create_backup(self.backup_template)
        self.backup_template.plan_backup_id = self.restore_plan
        lower = self.Command.create(
            {"name": "Lower", "action": "python_code", "access_level": "2"}
        )
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.backup_plan.write({"line_ids": [(0, 0, {"command_id": lower.id})]})
        backup.plan_log_ids.finish(0)
        self.backup_plan.write({"line_ids": [(0, 0, {"command_id": lower.id})]})

    def test_cleanup_counts_only_successful_per_jet(self):
        self.backup_template.keep_last = 1
        first = self._backup(create_date="2026-01-01 00:00:00")
        newest = self._backup(create_date="2026-01-02 00:00:00")
        failed = self._backup(state="failed")
        delete_failed = self._backup(state="delete_failed")
        orphan = self._backup(jet_id=False)
        self.Backup._run_cleanup()
        self.assertFalse(first.exists())
        self.assertFalse(failed.exists())
        self.assertTrue((newest | delete_failed | orphan).exists())
        self.backup_template.keep_last = 0
        failed = self._backup(state="failed", jet_id=False, server_id=False)
        self.Backup._run_cleanup()
        self.assertFalse(failed.exists())

    def test_waypoint_lifecycle_manager_and_access(self):
        template = self.env["cx.tower.jet.waypoint.template"].create(
            {
                "name": "Backup waypoint",
                "jet_template_id": self.template.id,
                "backup_template_id": self.backup_template.id,
                "access_level": "2",
                "plan_arrive_id": self.restore_plan.id,
                "plan_leave_id": self.restore_plan.id,
            }
        )
        waypoint = (
            self.env["cx.tower.jet.waypoint"]
            .with_user(self.manager)
            .create(
                {
                    "name": "Backup waypoint",
                    "jet_id": self.source.id,
                    "waypoint_template_id": template.id,
                }
            )
        )
        waypoint.prepare()
        self.assertEqual(waypoint.state, "ready")
        backup = waypoint.sudo().backup_id
        self.assertEqual(backup.state, "done")
        self.assertTrue(waypoint._is_backup_waypoint())
        waypoint.fly_to()
        self.assertEqual(waypoint.state, "current")
        waypoint._leave()
        self.assertEqual(waypoint.state, "ready")
        for record, field in (
            (backup, "state"),
            (self.backup_template, "name"),
            (self.source, "backup_count"),
            (waypoint, "backup_id"),
        ):
            with self.assertRaises(AccessError):
                record.with_user(self.manager).read([field])
        with self.assertRaises(ValidationError):
            backup.unlink()
        # Another Manager must not delete the creator's waypoint.
        other = self.Users.create(
            {
                "name": "Other Manager",
                "login": "backup_other_manager",
                "groups_id": [(4, self.group_manager.id)],
            }
        )
        self.template.manager_ids |= other
        with self.assertRaises(AccessError):
            waypoint.with_user(other).unlink()
        self.assertTrue(backup.exists())
        template.backup_template_id = False
        self.assertNotIn("__backup", waypoint._get_custom_variable_values())
        self.backup_template.plan_delete_id = self.delete_plan
        waypoint.unlink()
        self.assertFalse(waypoint.exists())
        self.assertFalse(backup.exists())

    def test_scheduled_task_constraints_and_manager_run(self):
        task = self.env["cx.tower.scheduled.task"].create(
            {
                "name": "Back up Jets",
                "action": "backup",
                "backup_template_id": self.backup_template.id,
                "jet_ids": [(4, self.source.id)],
                "manager_ids": [(4, self.manager.id)],
            }
        )
        task.with_user(self.manager).write({"jet_ids": [(6, 0, self.source.ids)]})
        task.with_user(self.manager).action_run()
        backup = self.Backup.search([("jet_id", "=", self.source.id)])
        self.assertEqual(backup.state, "done")
        self.assertEqual(backup.plan_log_ids.scheduled_task_id, task)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            task.server_ids = self.server_test_1
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            task.jet_ids = self.jet_sample
        empty = task.copy({"backup_template_id": False})
        self.assertEqual(empty._run_action(), [])

    def test_command_completion_no_values_leak_and_stop(self):
        command = self.Command.create(
            {
                "name": "Create backup",
                "action": "create_backup",
                "backup_template_id": self.backup_template.id,
            }
        )
        caller = self.Plan.create(
            {"name": "Caller", "line_ids": [(0, 0, {"command_id": command.id})]}
        )
        log = self.source.run_flight_plan(caller, variable_values={"bucket": "test"})
        backup = self.Backup.search([("jet_id", "=", self.source.id)])
        self.assertEqual(backup.state, "done")
        self.assertFalse(log.is_running)
        self.assertEqual(log.variable_values, {"bucket": "test"})
        self.assertEqual(log.command_log_ids.variable_values, {"bucket": "test"})
        self.assertFalse(log.has_backup_values)
        self.assertFalse(log.command_log_ids.has_backup_values)
        # Defer Backup lines while executing the Create Backup runner inline.
        original = type(self.server_test_1)._get_command_defer_handlers

        def handlers(server):
            return original(server) + [
                (1, lambda command, *args, **kwargs: command.action == "python_code")
            ]

        with patch.object(
            type(self.server_test_1), "_get_command_defer_handlers", handlers
        ):
            log2 = self.source.run_flight_plan(caller)
        waiting = log2.command_log_ids
        self.assertTrue(waiting.is_running)
        self.assertTrue(waiting.triggered_plan_log_id.is_running)
        waiting.stop()
        stopped = self.Backup.search([("created_from_command_log_id", "=", waiting.id)])
        self.assertEqual(stopped.state, "failed")
        self.assertEqual(waiting.command_status, -510)

    def test_subplan_provenance_survives_custom_values_rewrite(self):
        sub = self._make_plan("Sub", "custom_values.clear()")
        plan_command = self.Command.create(
            {
                "name": "Sub-plan",
                "action": "plan",
                "access_level": "3",
                "flight_plan_id": sub.id,
            }
        )
        self.backup_plan.write(
            {"line_ids": [(0, 0, {"command_id": plan_command.id, "sequence": 20})]}
        )
        backup = self.source.create_backup(self.backup_template)
        child = self.PlanLog.search(
            [("parent_flight_plan_log_id", "in", backup.plan_log_ids.ids)]
        )
        self.assertTrue(child.has_backup_values)
        self.assertTrue(all(child.command_log_ids.mapped("has_backup_values")))
        self.assertEqual(backup.state, "done")
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            sub.access_level = "2"

    def test_wizards_creator_only(self):
        backup = self._backup()
        other = self.Users.create(
            {
                "name": "Other Root",
                "login": "backup_other_root",
                "groups_id": [(4, self.group_root.id)],
            }
        )
        for model, values in (
            (
                "cx.tower.backup.restore.wizard",
                {"backup_id": backup.id, "server_id": self.server_test_1.id},
            ),
            (
                "cx.tower.backup.create.wizard",
                {
                    "jet_id": self.source.id,
                    "backup_template_id": self.backup_template.id,
                },
            ),
        ):
            wizard = self.env[model].with_user(self.root).create(values)
            with self.assertRaises(AccessError):
                wizard.with_user(other).read()
            with self.assertRaises(AccessError):
                wizard.with_user(other).action_confirm()

    def test_api_private_decorators_and_python_calls(self):
        from odoo.service.model import get_public_method

        for model in ("cx.tower.command.log", "cx.tower.plan.log"):
            for method in ("start", "finish", "record"):
                with self.assertRaises(AccessError):
                    get_public_method(self.env[model], method)
            self.assertTrue(callable(get_public_method(self.env[model], "stop")))
        self.assertTrue(
            callable(get_public_method(self.env["cx.tower.plan.log"], "action_stop"))
        )
        with self.assertRaises(AccessError):
            get_public_method(self.source, "create_backup")

    def test_yaml_fresh_roundtrip_and_forward_scheduled_task(self):
        variable = self.Variable.create({"name": "Export backup variable"})
        self.backup_template.write(
            {
                "backup_available_variable_ids": [(6, 0, variable.ids)],
                "restore_available_variable_ids": [(6, 0, variable.ids)],
            }
        )
        waypoint = self.env["cx.tower.jet.waypoint.template"].create(
            {
                "name": "Export backup waypoint",
                "jet_template_id": self.template.id,
                "backup_template_id": self.backup_template.id,
            }
        )
        command = self.Command.create(
            {
                "name": "Export backup command",
                "action": "create_backup",
                "backup_template_id": self.backup_template.id,
            }
        )
        caller = self.Plan.create(
            {
                "name": "Export backup caller",
                "line_ids": [(0, 0, {"command_id": command.id})],
            }
        )
        self.template.plan_clone_same_server_id = caller
        wizard = (
            self.env["cx.tower.yaml.export.wiz"]
            .with_context(
                active_model=self.template._name, active_ids=self.template.ids
            )
            .create({"include_related_records": True})
        )
        wizard.onchange_include_related_records()
        document = yaml.safe_load(wizard.yaml_code)
        references = {}

        def collect(value):
            if isinstance(value, dict):
                if value.get("reference"):
                    references[value["reference"]] = value["reference"] + "_fresh"
                for child in value.values():
                    collect(child)
            elif isinstance(value, list):
                for child in value:
                    collect(child)

        def rename(value):
            if isinstance(value, dict):
                return {key: rename(child) for key, child in value.items()}
            if isinstance(value, list):
                return [rename(child) for child in value]
            return references.get(value, value) if isinstance(value, str) else value

        collect(document["records"])
        document = rename(document)
        document["records"].insert(
            0,
            {
                "cetmix_tower_model": "scheduled_task",
                "reference": "backup_forward_task",
                "name": "Forward Backup task",
                "action": "backup",
                "backup_template_id": references[self.backup_template.reference],
            },
        )
        importer = self.env["cx.tower.yaml.import.wiz"].create(
            {
                "if_record_exists": "update",
                "yaml_code": yaml.safe_dump(document),
            }
        )
        importer.action_import_yaml()
        copied = self.JetTemplate.get_by_reference(references[self.template.reference])
        self.assertTrue(copied)
        self.assertEqual(len(copied.backup_template_ids), 1)
        copied_template = copied.backup_template_ids
        self.assertEqual(copied_template.jet_template_id, copied)
        self.assertEqual(copied_template.backup_available_variable_ids, variable)
        self.assertEqual(copied_template.restore_available_variable_ids, variable)
        task = self.env["cx.tower.scheduled.task"].get_by_reference(
            "backup_forward_task"
        )
        self.assertEqual(task.backup_template_id, copied_template)
        self.assertEqual(
            copied.waypoint_template_ids.backup_template_id, copied_template
        )
        self.assertNotEqual(copied.waypoint_template_ids, waypoint)
        self.assertEqual(
            copied.plan_clone_same_server_id.line_ids.command_id.backup_template_id,
            copied_template,
        )

    def test_schedule_partial_writes_roll_back_per_jet(self):
        second = self.template.create_jet(self.server_test_1, name="Second backup Jet")
        task = self.env["cx.tower.scheduled.task"].create(
            {
                "name": "Partial failures",
                "action": "backup",
                "backup_template_id": self.backup_template.id,
                "jet_ids": [(6, 0, (self.source | second).ids)],
            }
        )
        original = type(self.source).create_backup

        def capture(jet, *args, **kwargs):
            backup = original(jet, *args, **kwargs)
            if jet == self.source:
                raise ValidationError(_("failure after snapshot"))
            return backup

        with (
            patch.object(type(self.source), "create_backup", capture),
            mute_logger(
                "odoo.addons.cetmix_tower_backup.models.cx_tower_scheduled_task"
            ),
        ):
            result = task.action_run()
        self.assertIn("failure after snapshot", result["params"]["message"])
        self.assertFalse(self.Backup.search([("jet_id", "=", self.source.id)]))
        self.assertEqual(self.Backup.search([("jet_id", "=", second.id)]).state, "done")

    def test_command_exit_codes_and_dispatch_rollback(self):
        command = self.Command.create(
            {"name": "Missing backup", "action": "create_backup"}
        )
        self.server_test_1.run_command(command)
        server_log = self.CommandLog.search(
            [("command_id", "=", command.id)], order="id desc", limit=1
        )
        self.assertEqual(server_log.command_status, -503)
        self.source.run_command(command)
        log = self.CommandLog.search(
            [("command_id", "=", command.id)], order="id desc", limit=1
        )
        self.assertEqual(log.command_status, -509)
        command.backup_template_id = self.backup_template
        self.backup_plan.line_ids.path = "{{ broken"
        self.source.run_command(command)
        log = self.CommandLog.search(
            [("command_id", "=", command.id)], order="id desc", limit=1
        )
        self.assertEqual(log.command_status, -510)
        self.assertFalse(self.source.active_backup_id)
        self.assertFalse(self.Backup.search([("jet_id", "=", self.source.id)]))
        self.assertFalse(
            self.PlanLog.search(
                [("plan_id", "=", self.backup_plan.id), ("is_running", "=", True)]
            )
        )

    def test_backup_result_survives_caller_dispatch_error(self):
        command = self.Command.create(
            {
                "name": "Back up",
                "action": "create_backup",
                "backup_template_id": self.backup_template.id,
            }
        )
        next_command = self.Command.create(
            {"name": "Next", "action": "python_code", "code": "result = {}"}
        )
        caller = self.Plan.create(
            {
                "name": "Caller error",
                "line_ids": [
                    (0, 0, {"command_id": command.id, "sequence": 10}),
                    (
                        0,
                        0,
                        {
                            "command_id": next_command.id,
                            "sequence": 20,
                            "path": "{{ broken",
                        },
                    ),
                ],
            }
        )
        with mute_logger("odoo.addons.cetmix_tower_backup.models.cx_tower_backup"):
            self.source.run_flight_plan(caller)
        backup = self.Backup.search([("jet_id", "=", self.source.id)])
        self.assertEqual(backup.state, "done")
        self.assertFalse(backup.plan_log_ids.is_running)

    def test_recursive_backup_command_terminates(self):
        command = self.Command.create(
            {
                "name": "Recursive backup",
                "action": "create_backup",
                "backup_template_id": self.backup_template.id,
                "access_level": "3",
            }
        )
        self.backup_plan.write(
            {
                "allow_parallel_run": True,
                "line_ids": [
                    (5, 0, 0),
                    (0, 0, {"command_id": command.id}),
                ],
            }
        )
        backup = self.source.create_backup(self.backup_template)
        backups = self.Backup.search([("jet_id", "=", self.source.id)])
        self.assertEqual(len(backups), 1)
        self.assertEqual(backup.state, "failed")
        self.assertEqual(set(backups.mapped("state")), {"failed"})

    def test_action_switch_to_lower_subplan_is_rejected(self):
        lower = self._make_plan("Lower sub-plan", "result = {}", access_level="2")
        command = self.backup_plan.line_ids.command_id
        command.flight_plan_id = lower
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            command.action = "plan"

    def test_waypoint_busy_delete_and_jet_cascade(self):
        self.backup_template.plan_delete_id = self.delete_plan
        template = self.env["cx.tower.jet.waypoint.template"].create(
            {
                "name": "Backup owner",
                "jet_template_id": self.template.id,
                "backup_template_id": self.backup_template.id,
            }
        )
        waypoint = self.env["cx.tower.jet.waypoint"].create(
            {
                "name": "Backup owner",
                "jet_id": self.source.id,
                "waypoint_template_id": template.id,
            }
        )
        waypoint.prepare()
        backup = waypoint.backup_id
        with self._defer():
            busy = self.source.run_flight_plan(self.delete_plan)
        with self.assertRaises(ValidationError):
            waypoint.unlink()
        self.assertEqual(waypoint.state, "ready")
        self.assertEqual(backup.state, "done")
        busy.command_log_ids.finish(status=0)
        self.source.unlink()
        self.assertFalse(waypoint.exists())
        self.assertTrue(backup.exists())
        self.assertFalse(backup.waypoint_ids)

    def test_queued_create_backup_finishes_through_callback(self):
        if "queue_job_id" not in self.CommandLog._fields:
            self.skipTest("Requires cetmix_tower_server_queue")
        from odoo.addons.queue_job.tests.common import trap_jobs

        command = self.Command.create(
            {
                "name": "Queued backup",
                "action": "create_backup",
                "backup_template_id": self.backup_template.id,
            }
        )
        caller = self.Plan.create(
            {"name": "Queued caller", "line_ids": [(0, 0, {"command_id": command.id})]}
        )

        def handlers(server):
            return [(50, server._try_defer_command_queue)]

        with (
            patch.object(
                type(self.server_test_1), "_get_command_defer_handlers", handlers
            ),
            trap_jobs() as trap,
        ):
            log = self.source.run_flight_plan(caller)
            self.assertTrue(log.is_running)
            trap.perform_enqueued_jobs()
            self.assertTrue(log.command_log_ids.is_running)
            self.assertEqual(len(trap.enqueued_jobs), 1)
            trap.perform_enqueued_jobs()
            self.assertFalse(trap.enqueued_jobs)
            backup = self.Backup.search(
                [("created_from_command_log_id", "in", log.command_log_ids.ids)]
            )
            self.assertEqual(backup.state, "done")
            self.assertFalse(log.command_log_ids.is_running)
            self.assertEqual(log.command_log_ids.command_status, 0)

    def test_archived_plan_commands_still_require_root(self):
        archived = self._make_plan("Archived backup", "result = {}")
        archived.active = False
        archived.with_context(active_test=False).line_ids.command_id.access_level = "2"
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.backup_template.plan_backup_id = archived

    def test_waypoint_async_failure_and_create_waypoint_command(self):
        template = self.env["cx.tower.jet.waypoint.template"].create(
            {
                "name": "Async backup waypoint",
                "jet_template_id": self.template.id,
                "backup_template_id": self.backup_template.id,
            }
        )
        command = self.Command.create(
            {
                "name": "Create backup waypoint",
                "action": "create_waypoint",
                "waypoint_template_id": template.id,
            }
        )
        caller = self.Plan.create(
            {
                "name": "Create backup waypoint caller",
                "line_ids": [(0, 0, {"command_id": command.id})],
            }
        )

        def handlers(server):
            return [
                (1, lambda command, *args, **kwargs: command.action == "python_code")
            ]

        with patch.object(
            type(self.server_test_1), "_get_command_defer_handlers", handlers
        ):
            log = self.source.run_flight_plan(caller)
        waypoint = self.source.waypoint_ids
        backup = waypoint.backup_id
        self.assertEqual(waypoint.state, "preparing")
        self.assertEqual(backup.state, "running")
        self.assertTrue(log.command_log_ids.is_running)
        backup.plan_log_ids.command_log_ids.finish(status=-1)
        self.assertEqual(backup.state, "failed")
        self.assertEqual(waypoint.state, "error")
        self.assertFalse(log.command_log_ids.is_running)
        self.assertEqual(log.command_log_ids.command_status, -508)
        self.Backup._run_cleanup()
        self.assertTrue(backup.exists())
        waypoint.with_context(
            backup_force_delete=True, backup_from_waypoint=True
        ).unlink()
        self.assertFalse(backup.exists())
        self.assertFalse(waypoint.exists())

    def test_wizard_owners_can_back_up_and_restore(self):
        wizard = (
            self.env["cx.tower.backup.create.wizard"]
            .with_user(self.root)
            .create(
                {
                    "jet_id": self.source.id,
                    "backup_template_id": self.backup_template.id,
                }
            )
        )
        action = wizard.action_confirm()
        backup = self.Backup.browse(action["res_id"])
        self.assertEqual(backup.state, "done")
        restore = (
            self.env["cx.tower.backup.restore.wizard"]
            .with_user(self.root)
            .create(
                {
                    "backup_id": backup.id,
                    "server_id": self.server_test_1.id,
                }
            )
        )
        action = restore.action_confirm()
        jet = self.Jet.browse(action["res_id"])
        self.assertTrue(jet.exists())
        self.assertNotEqual(jet, self.source)
        self.assertEqual(jet.jet_template_id, self.template)

    def test_wizard_custom_values_are_limited_and_replayed(self):
        variable = self.Variable.create(
            {"name": "Backup destination", "reference": "backup_destination"}
        )
        self.backup_template.write(
            {
                "backup_available_variable_ids": [(6, 0, variable.ids)],
                "restore_available_variable_ids": [(6, 0, variable.ids)],
            }
        )
        wizard = self.env["cx.tower.backup.create.wizard"].create(
            {
                "jet_id": self.source.id,
                "backup_template_id": self.backup_template.id,
                "line_ids": [
                    (0, 0, {"variable_id": variable.id, "value_char": "original"})
                ],
            }
        )
        backup = self.Backup.browse(wizard.action_confirm()["res_id"])
        self.assertEqual(
            backup.custom_variable_values, {variable.reference: "original"}
        )
        self.assertEqual(
            backup.plan_log_ids.variable_values[variable.reference], "original"
        )
        restore = self.env["cx.tower.backup.restore.wizard"].create(
            {
                "backup_id": backup.id,
                "server_id": self.server_test_1.id,
                "line_ids": [
                    (0, 0, {"variable_id": variable.id, "value_char": "override"})
                ],
            }
        )
        restore.action_confirm()
        restore_log = backup.plan_log_ids.filtered(
            lambda log: log.backup_operation == "restore"
        )
        self.assertEqual(restore_log.variable_values[variable.reference], "override")
        self.assertEqual(backup.custom_variable_values[variable.reference], "original")
        self.backup_template.write(
            {
                "backup_available_variable_ids": [(5, 0, 0)],
                "restore_available_variable_ids": [(5, 0, 0)],
            }
        )
        for dialog in (wizard, restore):
            with self.assertRaises(ValidationError):
                dialog.action_confirm()
        self.backup_template.write(
            {
                "backup_available_variable_ids": [(6, 0, variable.ids)],
                "restore_available_variable_ids": [(6, 0, variable.ids)],
            }
        )
        wizard.line_ids = [
            (0, 0, {"variable_id": variable.id, "value_char": "duplicate"})
        ]
        with self.assertRaises(ValidationError):
            wizard.action_confirm()

    def test_wizards_use_independent_available_variables(self):
        backup_variable = self.Variable.create({"name": "Backup only"})
        restore_variable = self.Variable.create({"name": "Restore only"})
        self.backup_template.write(
            {
                "backup_available_variable_ids": [(6, 0, backup_variable.ids)],
                "restore_available_variable_ids": [(6, 0, restore_variable.ids)],
            }
        )
        create = self.env["cx.tower.backup.create.wizard"].create(
            {
                "jet_id": self.source.id,
                "backup_template_id": self.backup_template.id,
                "line_ids": [
                    (0, 0, {"variable_id": restore_variable.id, "value_char": "wrong"})
                ],
            }
        )
        self.assertEqual(create.available_variable_ids, backup_variable)
        with self.assertRaises(ValidationError):
            create.action_confirm()
        create.line_ids.write(
            {"variable_id": backup_variable.id, "value_char": "backup"}
        )
        backup = self.Backup.browse(create.action_confirm()["res_id"])
        self.assertEqual(
            backup.custom_variable_values, {backup_variable.reference: "backup"}
        )
        restore = self.env["cx.tower.backup.restore.wizard"].create(
            {
                "backup_id": backup.id,
                "server_id": self.server_test_1.id,
                "line_ids": [
                    (0, 0, {"variable_id": backup_variable.id, "value_char": "wrong"})
                ],
            }
        )
        self.assertEqual(restore.available_variable_ids, restore_variable)
        with self.assertRaises(ValidationError):
            restore.action_confirm()
        restore.line_ids.write(
            {"variable_id": restore_variable.id, "value_char": "restore"}
        )
        restore.action_confirm()
        log = backup.plan_log_ids.filtered(
            lambda log: log.backup_operation == "restore"
        )
        self.assertEqual(log.variable_values[restore_variable.reference], "restore")
        self.assertEqual(log.variable_values[backup_variable.reference], "backup")
        self.backup_template.backup_available_variable_ids = False
        self.assertFalse(create.available_variable_ids)
        self.assertEqual(restore.available_variable_ids, restore_variable)

    def test_wizard_options_use_only_valid_canonical_values(self):
        variable = self.Variable.create({"name": "Backup option", "variable_type": "o"})
        other = self.Variable.create({"name": "Foreign option", "variable_type": "o"})
        options = self.env["cx.tower.variable.option"]
        option = options.create(
            {"name": "Chosen", "variable_id": variable.id, "value_char": "canonical"}
        )
        foreign = options.create(
            {"name": "Foreign", "variable_id": other.id, "value_char": "wrong"}
        )
        self.backup_template.write(
            {
                "backup_available_variable_ids": [(6, 0, variable.ids)],
                "restore_available_variable_ids": [(6, 0, variable.ids)],
            }
        )
        for kind, values in (
            (
                "create",
                {
                    "jet_id": self.source.id,
                    "backup_template_id": self.backup_template.id,
                },
            ),
            (
                "restore",
                {"backup_id": self._backup().id, "server_id": self.server_test_1.id},
            ),
        ):
            wizard = self.env[f"cx.tower.backup.{kind}.wizard"].create(values)
            wizard.line_ids = [
                (
                    0,
                    0,
                    {
                        "variable_id": variable.id,
                        "option_id": option.id,
                        "value_char": "forged",
                    },
                )
            ]
            self.assertEqual(
                self.backup_template._get_wizard_variable_values(
                    wizard.line_ids, "backup" if kind == "create" else "restore"
                ),
                {variable.reference: "canonical"},
            )
            wizard.line_ids.option_id = foreign
            with self.assertRaises(ValidationError):
                wizard.action_confirm()
            wizard.line_ids.option_id = False
            with self.assertRaises(ValidationError):
                wizard.action_confirm()

    def test_wizard_variable_lines_are_creator_only(self):
        variable = self.Variable.create({"name": "Dialog variable"})
        other = self.Users.create(
            {
                "name": "Other dialog Root",
                "login": "backup_line_other",
                "groups_id": [(4, self.group_root.id)],
            }
        )
        for kind, values in (
            (
                "create",
                {
                    "jet_id": self.source.id,
                    "backup_template_id": self.backup_template.id,
                },
            ),
            (
                "restore",
                {"backup_id": self._backup().id, "server_id": self.server_test_1.id},
            ),
        ):
            wizard = (
                self.env[f"cx.tower.backup.{kind}.wizard"]
                .with_user(self.root)
                .create(values)
            )
            model = self.env[f"cx.tower.backup.{kind}.wizard.variable.line"]
            line = model.with_user(self.root).create(
                {"wizard_id": wizard.id, "variable_id": variable.id}
            )
            with self.assertRaises(AccessError):
                line.with_user(other).read()
            with self.assertRaises(AccessError):
                line.with_user(other).write({"value_char": "injected"})
            with self.assertRaises(AccessError), self.env.cr.savepoint():
                model.with_user(other).create(
                    {"wizard_id": wizard.id, "variable_id": variable.id}
                )

    def test_waypoint_no_raise_skips_destination_and_deletes_other_records(self):
        template = self.env["cx.tower.jet.waypoint.template"].create(
            {
                "name": "No-raise waypoint",
                "jet_template_id": self.template.id,
                "backup_template_id": self.backup_template.id,
            }
        )
        blocked_backup = self._backup()
        allowed_backup = self._backup()
        waypoints = self.env["cx.tower.jet.waypoint"].create(
            [
                {
                    "name": "Destination",
                    "jet_id": self.source.id,
                    "waypoint_template_id": template.id,
                    "state": "ready",
                    "is_destination": True,
                    "backup_id": blocked_backup.id,
                },
                {
                    "name": "Deletable",
                    "jet_id": self.source.id,
                    "waypoint_template_id": template.id,
                    "state": "ready",
                    "backup_id": allowed_backup.id,
                },
            ]
        )
        with self.assertRaises(ValidationError):
            waypoints.unlink()
        self.assertEqual(len(waypoints.exists()), 2)
        with self.assertLogs(
            "odoo.addons.cetmix_tower_backup.models.cx_tower_jet_waypoint",
            level="ERROR",
        ):
            waypoints.with_context(waypoint_no_raise_on_delete=True).unlink()
        self.assertTrue(waypoints[0].exists())
        self.assertEqual(waypoints[0].state, "ready")
        self.assertTrue(blocked_backup.exists())
        self.assertFalse(waypoints[1].exists())
        self.assertFalse(allowed_backup.exists())

    def test_waypoint_no_raise_skips_busy_delete_without_hiding_access_errors(self):
        self.backup_template.plan_delete_id = self.delete_plan
        template = self.env["cx.tower.jet.waypoint.template"].create(
            {
                "name": "Busy no-raise waypoint",
                "jet_template_id": self.template.id,
                "backup_template_id": self.backup_template.id,
            }
        )
        backup = self._backup()
        waypoint = self.env["cx.tower.jet.waypoint"].create(
            {
                "name": "Busy",
                "jet_id": self.source.id,
                "state": "ready",
                "waypoint_template_id": template.id,
                "backup_id": backup.id,
            }
        )
        with self.assertRaises(AccessError):
            waypoint.with_user(self.manager).with_context(
                waypoint_no_raise_on_delete=True
            ).unlink()
        with self._defer():
            busy_log = self.source.run_flight_plan(self.delete_plan)
        with self.assertRaises(ValidationError):
            waypoint.unlink()
        with self.assertLogs(
            "odoo.addons.cetmix_tower_backup.models.cx_tower_jet_waypoint",
            level="ERROR",
        ):
            waypoint.with_context(waypoint_no_raise_on_delete=True).unlink()
        self.assertEqual(waypoint.state, "ready")
        self.assertEqual(backup.state, "done")
        self.assertTrue(busy_log.is_running)
        busy_log.command_log_ids.finish(status=0)
        waypoint.unlink()
        self.assertFalse(waypoint.exists())
        self.assertFalse(backup.exists())


@tagged("post_install", "-at_install")
class TestBackupClaimTransactions(TransactionCase):
    def test_row_claim_rejects_locked_and_stale_snapshot_admission(self):
        """Real independent transactions cannot admit an overlapping operation."""
        database = sql_db.db_connect(self.env.cr.dbname)
        with database.cursor() as setup_cr:
            setup_env = api.Environment(
                setup_cr,
                SUPERUSER_ID,
                {"tracking_disable": True, "skip_ssh_settings_check": True},
            )
            server = setup_env["cx.tower.server"].create(
                {
                    "name": "Backup claim concurrency server",
                    "ssh_auth_mode": "p",
                    "ssh_username": "test",
                }
            )
            template = setup_env["cx.tower.jet.template"].create(
                {"name": "Backup claim concurrency template"}
            )
            jet = setup_env["cx.tower.jet"].create(
                {
                    "name": "Backup claim concurrency Jet",
                    "server_id": server.id,
                    "jet_template_id": template.id,
                }
            )
            command = setup_env["cx.tower.command"].create(
                {
                    "name": "Backup claim concurrency command",
                    "access_level": "3",
                    "action": "python_code",
                    "code": "result = {'exit_code': 0}",
                }
            )
            plan = setup_env["cx.tower.plan"].create(
                {
                    "name": "Backup claim concurrency plan",
                    "access_level": "3",
                    "line_ids": [(0, 0, {"command_id": command.id})],
                }
            )
            backup_template = setup_env["cx.tower.backup.template"].create(
                {
                    "name": "Backup claim concurrency backup template",
                    "jet_template_id": template.id,
                    "plan_backup_id": plan.id,
                    "plan_restore_id": plan.id,
                }
            )
            ids = {
                "server": server.id,
                "template": template.id,
                "jet": jet.id,
                "command": command.id,
                "plan": plan.id,
                "backup_template": backup_template.id,
            }
            # Independent transactions require committed, separately owned fixtures.
            setup_cr.commit()
        try:
            with database.cursor() as first_cr, database.cursor() as second_cr:
                first_env = api.Environment(first_cr, SUPERUSER_ID, {})
                second_env = api.Environment(second_cr, SUPERUSER_ID, {})
                first_jet = first_env["cx.tower.jet"].browse(ids["jet"])
                second_jet = second_env["cx.tower.jet"].browse(ids["jet"])
                self.assertFalse(second_jet.active_backup_id)
                with patch.object(
                    type(first_env["cx.tower.server"]),
                    "_get_command_defer_handlers",
                    return_value=[(1, lambda *args, **kwargs: True)],
                ):
                    backup = first_jet.create_backup(
                        first_env["cx.tower.backup.template"].browse(
                            ids["backup_template"]
                        )
                    )
                self.assertEqual(first_jet.active_backup_id, backup)
                with (
                    mute_logger("odoo.sql_db"),
                    self.assertRaises(errors.LockNotAvailable),
                    second_cr.savepoint(),
                ):
                    second_jet._check_backup_action_admission()
                # Publish the claim while request B keeps its original snapshot.
                first_cr.commit()
                with (
                    mute_logger("odoo.sql_db"),
                    self.assertRaises(errors.SerializationFailure),
                    second_cr.savepoint(),
                ):
                    second_jet._check_backup_action_admission()
                second_cr.rollback()
                second_env.invalidate_all()
                with self.assertRaises(ValidationError):
                    second_jet._check_backup_action_admission()
                second_cr.rollback()
        finally:
            with database.cursor() as cleanup_cr:
                cleanup_env = api.Environment(cleanup_cr, SUPERUSER_ID, {})
                jet = cleanup_env["cx.tower.jet"].browse(ids["jet"])
                jet.write({"active_backup_id": False})
                backups = cleanup_env["cx.tower.backup"].search(
                    [("jet_id", "=", jet.id)]
                )
                backups.write({"state": "failed"})
                backups.unlink()
                jet.unlink()
                cleanup_env["cx.tower.server"].browse(ids["server"]).unlink()
                cleanup_env["cx.tower.backup.template"].browse(
                    ids["backup_template"]
                ).unlink()
                cleanup_env["cx.tower.jet.template"].browse(ids["template"]).unlink()
                cleanup_env["cx.tower.plan"].browse(ids["plan"]).unlink()
                cleanup_env["cx.tower.command"].browse(ids["command"]).unlink()
                cleanup_cr.commit()
