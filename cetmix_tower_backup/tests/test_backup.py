# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from unittest.mock import patch

import yaml

from odoo import _
from odoo.exceptions import AccessError, ValidationError
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

    def test_failed_and_stopped_backup(self):
        for status in (-1, -308):
            with self._defer():
                backup = self.source.create_backup(self.backup_template)
            backup.plan_log_ids.command_log_ids.finish(status=status)
            self.assertEqual(backup.state, "failed")
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
        self.assertEqual(
            self.source.create_backup(self.backup_template, ignore_busy=True).state,
            "done",
        )
        with self.assertRaises(ValidationError):
            self.source.create_backup(self.backup_template, waypoint=self.waypoint)

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
        self.assertEqual(len(backups), 2)
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
