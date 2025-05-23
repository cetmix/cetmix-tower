# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields
from odoo.exceptions import AccessError

from .common import TestTowerCommon


class TestCxTowerScheduledTask(TestTowerCommon):
    """Test the cx.tower.scheduled.task model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create an additional server for multi-server command test
        cls.server_test_2 = cls.Server.create(
            {
                "name": "Test 2",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "host_key": "test_key",
                "os_id": cls.os_debian_10.id,
            }
        )

        # Scheduled task: command (multi-server)
        cls.command_scheduled_task = cls.ScheduledTask.create(
            {
                "name": "Test Command Scheduled Task",
                "action": "command",
                "command_id": cls.command_list_dir.id,
                "interval_number": 1,
                "interval_type": "days",
                "next_call": fields.Datetime.now(),
                "server_ids": [(6, 0, [cls.server_test_1.id, cls.server_test_2.id])],
            }
        )

        # Scheduled task: plan (single server)
        cls.plan_scheduled_task = cls.ScheduledTask.create(
            {
                "name": "Test Plan Scheduled Task",
                "action": "plan",
                "plan_id": cls.plan_1.id,
                "interval_number": 1,
                "interval_type": "days",
                "next_call": fields.Datetime.now(),
                "server_ids": [(6, 0, [cls.server_test_1.id])],
            }
        )

        # Custom variable for task (option type)
        cls.variable_odoo_versions = cls.Variable.create(
            {
                "name": "odoo_versions",
                "variable_type": "o",
            }
        )
        cls.variable_option_16_0 = cls.VariableOption.create(
            {
                "name": "16.0",
                "value_char": "16.0",
                "variable_id": cls.variable_odoo_versions.id,
            }
        )

        # Add custom variables to tasks
        cls.scheduled_task_cv_os = cls.ScheduledTaskCv.create(
            {
                "scheduled_task_id": cls.command_scheduled_task.id,
                "variable_id": cls.variable_os.id,
                "value_char": "Windows 2k",
            }
        )
        cls.scheduled_task_cv_version = cls.ScheduledTaskCv.create(
            {
                "scheduled_task_id": cls.command_scheduled_task.id,
                "variable_id": cls.variable_odoo_versions.id,
                "option_id": cls.variable_option_16_0.id,
            }
        )
        cls.scheduled_task_cv_version_plan = cls.ScheduledTaskCv.create(
            {
                "scheduled_task_id": cls.plan_scheduled_task.id,
                "variable_id": cls.variable_odoo_versions.id,
                "option_id": cls.variable_option_16_0.id,
            }
        )

    def _assert_log_records(self, log_model, scheduled_task, expected_count):
        """Helper: Assert that log records exist for the task"""
        logs = log_model.search([("scheduled_task_id", "=", scheduled_task.id)])
        self.assertTrue(logs, f"{log_model._name} logs should be created after run.")
        self.assertEqual(
            len(logs),
            expected_count,
            f"Expected {expected_count} logs for {scheduled_task.display_name}, "
            f"got {len(logs)}.",
        )

    def _assert_next_and_last_call_changed(
        self, task, last_call_before, next_call_before
    ):
        """Helper: Assert next_call and last_call changed after run"""
        task.invalidate_recordset()
        self.assertNotEqual(
            task.last_call, last_call_before, "last_call must be changed after run."
        )
        self.assertNotEqual(
            task.next_call, next_call_before, "next_call must be changed after run."
        )

    def test_reserve_tasks_atomic(self):
        """Scheduled Task: reserve_tasks must only lock available"""
        tasks = self.command_scheduled_task + self.plan_scheduled_task
        reserved = tasks._reserve_tasks()
        self.assertEqual(
            set(reserved.ids), set(tasks.ids), "Both tasks should be reserved"
        )
        # Repeated reservation should return empty (already running)
        tasks.invalidate_recordset()
        reserved_again = tasks._reserve_tasks()
        self.assertFalse(
            reserved_again, "Already reserved tasks must not be reserved again"
        )

    def test_run_task_command(self):
        """Running a scheduled command task creates logs per server."""
        logs_before = self.CommandLog.search(
            [("scheduled_task_id", "=", self.command_scheduled_task.id)]
        )
        self.assertFalse(logs_before, "No command logs should exist before run.")

        last_call_before = self.command_scheduled_task.last_call
        next_call_before = self.command_scheduled_task.next_call

        self.command_scheduled_task._run()
        self._assert_next_and_last_call_changed(
            self.command_scheduled_task, last_call_before, next_call_before
        )
        self._assert_log_records(
            self.CommandLog,
            self.command_scheduled_task,
            expected_count=len(self.command_scheduled_task.server_ids),
        )

    def test_run_task_plan(self):
        """Running a scheduled plan task creates one log per server."""
        logs_before = self.PlanLog.search(
            [("scheduled_task_id", "=", self.plan_scheduled_task.id)]
        )
        self.assertFalse(logs_before, "No plan logs should exist before run.")

        last_call_before = self.plan_scheduled_task.last_call
        next_call_before = self.plan_scheduled_task.next_call

        self.plan_scheduled_task._run()
        self._assert_next_and_last_call_changed(
            self.plan_scheduled_task, last_call_before, next_call_before
        )
        self._assert_log_records(
            self.PlanLog,
            self.plan_scheduled_task,
            expected_count=len(self.plan_scheduled_task.server_ids),
        )

    def test_user_write_create_unlink_access(self):
        """User: cannot create, write or unlink scheduled tasks."""
        with self.assertRaises(AccessError):
            self.ScheduledTask.with_user(self.user).create(
                {
                    "name": "Test",
                    "action": "command",
                    "command_id": self.command_list_dir.id,
                    "server_ids": [(6, 0, [self.server_test_1.id])],
                }
            )
        with self.assertRaises(AccessError):
            self.command_scheduled_task.with_user(self.user).write({"sequence": 33})
        with self.assertRaises(AccessError):
            self.command_scheduled_task.with_user(self.user).unlink()

    def test_manager_read_access(self):
        """Manager: can read scheduled task if in manager_ids or in server's
        manager_ids/user_ids."""
        self.command_scheduled_task.manager_ids = [(6, 0, [self.manager.id])]
        tasks = self.ScheduledTask.with_user(self.manager).search(
            [("id", "=", self.command_scheduled_task.id)]
        )
        self.assertIn(
            self.command_scheduled_task,
            tasks,
            "Manager should be able to read their task.",
        )

        # Remove from manager_ids, but add to server manager_ids
        self.command_scheduled_task.manager_ids = [(6, 0, [])]
        self.server_test_1.manager_ids = [(6, 0, [self.manager.id])]
        tasks = self.ScheduledTask.with_user(self.manager).search(
            [("id", "=", self.command_scheduled_task.id)]
        )
        self.assertIn(
            self.command_scheduled_task,
            tasks,
            "Manager should be able to read task via server manager_ids.",
        )

        # Remove manager from everywhere
        self.server_test_1.manager_ids = [(6, 0, [])]
        tasks = self.ScheduledTask.with_user(self.manager).search(
            [("id", "=", self.command_scheduled_task.id)]
        )
        self.assertNotIn(
            self.command_scheduled_task,
            tasks,
            "Manager should NOT be able to read task without relation.",
        )

    def test_manager_write_create_access(self):
        """Manager: can create/write if in manager_ids, else denied."""
        # Create as manager
        task = self.ScheduledTask.with_user(self.manager).create(
            {
                "name": "Test",
                "action": "command",
                "command_id": self.command_list_dir.id,
                "manager_ids": [(6, 0, [self.manager.id])],
                "server_ids": [(6, 0, [self.server_test_1.id])],
            }
        )
        try:
            task.with_user(self.manager).write({"sequence": 77})
        except AccessError:
            self.fail("Manager should be able to write their own scheduled tasks.")

        # Should fail if not in manager_ids
        self.command_scheduled_task.manager_ids = [(6, 0, [])]
        with self.assertRaises(AccessError):
            self.command_scheduled_task.with_user(self.manager).write({"sequence": 11})

    def test_manager_unlink_access(self):
        """Manager: can unlink only their own tasks (in manager_ids & creator)."""
        # Create as manager
        task = self.ScheduledTask.with_user(self.manager).create(
            {
                "name": "Test",
                "action": "command",
                "command_id": self.command_list_dir.id,
                "manager_ids": [(6, 0, [self.manager.id])],
                "server_ids": [(6, 0, [self.server_test_1.id])],
            }
        )
        try:
            task.with_user(self.manager).unlink()
        except AccessError:
            self.fail("Manager should be able to unlink their own task.")

        # Not creator
        with self.assertRaises(AccessError):
            self.command_scheduled_task.with_user(self.manager).unlink()

    def test_root_unrestricted_access(self):
        """Root: full unrestricted access to all scheduled tasks."""
        # Read
        tasks = self.ScheduledTask.with_user(self.root).search(
            [("id", "=", self.command_scheduled_task.id)]
        )
        self.assertIn(
            self.command_scheduled_task, tasks, "Root should be able to read any task."
        )

        # Create
        task = self.ScheduledTask.with_user(self.root).create(
            {
                "name": "Test",
                "action": "command",
                "command_id": self.command_list_dir.id,
                "server_ids": [(6, 0, [self.server_test_1.id])],
            }
        )
        try:
            task.with_user(self.root).write({"sequence": 123})
            task.with_user(self.root).unlink()
        except AccessError:
            self.fail("Root should be able to write/unlink any scheduled task.")
