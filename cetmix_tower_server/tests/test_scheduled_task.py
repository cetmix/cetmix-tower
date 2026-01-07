# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from datetime import datetime

from odoo import fields
from odoo.exceptions import AccessError, ValidationError

from .common import TestTowerCommon


class TestTowerScheduledTask(TestTowerCommon):
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

        # Create additional Jet Template for access testing
        cls.jet_template_test_access = cls.JetTemplate.create(
            {
                "name": "Test Jet Template for Access",
                "server_ids": [(4, cls.server_test_1.id)],
            }
        )

        # Create additional Jet for access testing
        cls.jet_test_access = cls.Jet.create(
            {
                "name": "Test Jet for Access",
                "jet_template_id": cls.jet_template_test_access.id,
                "server_id": cls.server_test_1.id,
            }
        )

        # Scheduled task with Jet and Jet Template for access testing
        cls.jet_scheduled_task = cls.ScheduledTask.create(
            {
                "name": "Test Jet Scheduled Task",
                "action": "command",
                "command_id": cls.command_list_dir.id,
                "interval_number": 1,
                "interval_type": "days",
                "next_call": fields.Datetime.now(),
                "jet_ids": [(6, 0, [cls.jet_test_access.id])],
                "jet_template_ids": [(6, 0, [cls.jet_template_test_access.id])],
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

    def _clear_all_access(
        self,
        scheduled_task,
        jet=None,
        jet_template=None,
        server=None,
        server_template=None,
    ):
        """Helper: Clear all access paths for a scheduled task and related objects."""
        scheduled_task.manager_ids = [(5, 0, 0)]
        scheduled_task.user_ids = [(5, 0, 0)]
        if jet:
            jet.manager_ids = [(5, 0, 0)]
            jet.user_ids = [(5, 0, 0)]
        if jet_template:
            jet_template.manager_ids = [(5, 0, 0)]
            jet_template.user_ids = [(5, 0, 0)]
        if server:
            server.manager_ids = [(5, 0, 0)]
            server.user_ids = [(5, 0, 0)]
        if server_template:
            server_template.manager_ids = [(5, 0, 0)]
            server_template.user_ids = [(5, 0, 0)]

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
        self.command_scheduled_task.manager_ids = [(5, 0, 0)]
        self.server_test_1.manager_ids = [(6, 0, [self.manager.id])]
        tasks = self.ScheduledTask.with_user(self.manager).search(
            [("id", "=", self.command_scheduled_task.id)]
        )
        self.assertIn(
            self.command_scheduled_task,
            tasks,
            "Manager should be able to read task via server manager_ids.",
        )

        # Test server user_ids access
        self.server_test_1.manager_ids = [(5, 0, 0)]
        self.server_test_1.user_ids = [(6, 0, [self.manager.id])]
        tasks = self.ScheduledTask.with_user(self.manager).search(
            [("id", "=", self.command_scheduled_task.id)]
        )
        self.assertIn(
            self.command_scheduled_task,
            tasks,
            "Manager should be able to read task via server user_ids.",
        )

        # Remove manager from everywhere
        self._clear_all_access(self.command_scheduled_task, server=self.server_test_1)
        tasks = self.ScheduledTask.with_user(self.manager).search(
            [("id", "=", self.command_scheduled_task.id)]
        )
        self.assertNotIn(
            self.command_scheduled_task,
            tasks,
            "Manager should NOT be able to read task without relation.",
        )

    def test_manager_read_access_via_jet(self):
        """Manager: can read scheduled task if in jet's user_ids/manager_ids."""
        # Test access via jet manager_ids
        self.jet_test_access.manager_ids = [(6, 0, [self.manager.id])]
        tasks = self.ScheduledTask.with_user(self.manager).search(
            [("id", "=", self.jet_scheduled_task.id)]
        )
        self.assertIn(
            self.jet_scheduled_task,
            tasks,
            "Manager should be able to read task via jet manager_ids.",
        )

        # Test access via jet user_ids
        self.jet_test_access.manager_ids = [(5, 0, 0)]
        self.jet_test_access.user_ids = [(6, 0, [self.manager.id])]
        tasks = self.ScheduledTask.with_user(self.manager).search(
            [("id", "=", self.jet_scheduled_task.id)]
        )
        self.assertIn(
            self.jet_scheduled_task,
            tasks,
            "Manager should be able to read task via jet user_ids.",
        )

        # Test access via jet_template manager_ids
        self.jet_test_access.user_ids = [(5, 0, 0)]
        self.jet_template_test_access.manager_ids = [(6, 0, [self.manager.id])]
        tasks = self.ScheduledTask.with_user(self.manager).search(
            [("id", "=", self.jet_scheduled_task.id)]
        )
        self.assertIn(
            self.jet_scheduled_task,
            tasks,
            "Manager should be able to read task via jet_template manager_ids.",
        )

        # Test access via jet_template user_ids
        self.jet_template_test_access.manager_ids = [(5, 0, 0)]
        self.jet_template_test_access.user_ids = [(6, 0, [self.manager.id])]
        tasks = self.ScheduledTask.with_user(self.manager).search(
            [("id", "=", self.jet_scheduled_task.id)]
        )
        self.assertIn(
            self.jet_scheduled_task,
            tasks,
            "Manager should be able to read task via jet_template user_ids.",
        )

        # Remove manager from everywhere
        self._clear_all_access(
            self.jet_scheduled_task,
            jet=self.jet_test_access,
            jet_template=self.jet_template_test_access,
            server=self.server_test_1,
        )
        tasks = self.ScheduledTask.with_user(self.manager).search(
            [("id", "=", self.jet_scheduled_task.id)]
        )
        self.assertNotIn(
            self.jet_scheduled_task,
            tasks,
            "Manager should NOT be able to read task without relation.",
        )

    def test_manager_read_access_via_server_template(self):
        """Manager: can read scheduled task if in server_template's
        user_ids/manager_ids."""
        # Create scheduled task with server template
        server_template_task = self.ScheduledTask.create(
            {
                "name": "Test Server Template Scheduled Task",
                "action": "command",
                "command_id": self.command_list_dir.id,
                "interval_number": 1,
                "interval_type": "days",
                "next_call": fields.Datetime.now(),
                "server_template_ids": [(6, 0, [self.server_template_sample.id])],
            }
        )

        # Test access via server_template manager_ids
        self.server_template_sample.manager_ids = [(6, 0, [self.manager.id])]
        tasks = self.ScheduledTask.with_user(self.manager).search(
            [("id", "=", server_template_task.id)]
        )
        self.assertIn(
            server_template_task,
            tasks,
            "Manager should be able to read task via server_template manager_ids.",
        )

        # Test access via server_template user_ids
        self.server_template_sample.manager_ids = [(5, 0, 0)]
        self.server_template_sample.user_ids = [(6, 0, [self.manager.id])]
        tasks = self.ScheduledTask.with_user(self.manager).search(
            [("id", "=", server_template_task.id)]
        )
        self.assertIn(
            server_template_task,
            tasks,
            "Manager should be able to read task via server_template user_ids.",
        )

        # Remove manager from everywhere
        self._clear_all_access(
            server_template_task,
            server_template=self.server_template_sample,
            server=self.server_test_1,
        )
        tasks = self.ScheduledTask.with_user(self.manager).search(
            [("id", "=", server_template_task.id)]
        )
        self.assertNotIn(
            server_template_task,
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
        self.command_scheduled_task.manager_ids = [(5, 0, 0)]
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

    def test_get_next_call_dow_wednesday(self):
        """Test _get_next_call_dow when today is Wednesday.
        Task runs Monday, Wednesday, Friday -> should return Friday."""
        # Create task with Monday, Wednesday, Friday selected
        task = self.ScheduledTask.create(
            {
                "name": "Test DOW Task",
                "action": "command",
                "command_id": self.command_list_dir.id,
                "interval_type": "dow",
                "monday": True,
                "wednesday": True,
                "friday": True,
                "server_ids": [(6, 0, [self.server_test_1.id])],
            }
        )

        # Create a Wednesday datetime (2024-01-03 is a Wednesday)
        # Set time to 10:30:45
        wednesday_date = datetime(2024, 1, 3, 10, 30, 45)

        # Calculate next call
        next_call = task._get_next_call_dow(task, wednesday_date)

        # Should be Friday (2 days ahead) at the same time
        expected_friday = datetime(2024, 1, 5, 10, 30, 45)
        self.assertEqual(
            next_call,
            expected_friday,
            "Next call from Wednesday should be Friday at the same time.",
        )

    def test_get_next_call_dow_friday(self):
        """Test _get_next_call_dow when today is Friday.
        Task runs Monday, Wednesday, Friday -> should return Monday (next week)."""
        # Create task with Monday, Wednesday, Friday selected
        task = self.ScheduledTask.create(
            {
                "name": "Test DOW Task",
                "action": "command",
                "command_id": self.command_list_dir.id,
                "interval_type": "dow",
                "monday": True,
                "wednesday": True,
                "friday": True,
                "server_ids": [(6, 0, [self.server_test_1.id])],
            }
        )

        # Create a Friday datetime (2024-01-05 is a Friday)
        # Set time to 14:15:30
        friday_date = datetime(2024, 1, 5, 14, 15, 30)

        # Calculate next call
        next_call = task._get_next_call_dow(task, friday_date)

        # Should be Monday next week (3 days ahead) at the same time
        expected_monday = datetime(2024, 1, 8, 14, 15, 30)
        self.assertEqual(
            next_call,
            expected_monday,
            "Next call from Friday should be Monday next week at the same time.",
        )

    def test_check_days_of_week_constraint(self):
        """
        Test _check_days_of_week constraint:
        no days selected should raise ValidationError.
        """
        # Try to create a task with interval_type="dow" but no days selected
        with self.assertRaises(ValidationError) as context:
            self.ScheduledTask.create(
                {
                    "name": "Test DOW Task No Days",
                    "action": "command",
                    "command_id": self.command_list_dir.id,
                    "interval_type": "dow",
                    "monday": False,
                    "tuesday": False,
                    "wednesday": False,
                    "thursday": False,
                    "friday": False,
                    "saturday": False,
                    "sunday": False,
                    "server_ids": [(6, 0, [self.server_test_1.id])],
                }
            )
        self.assertIn(
            "At least one day of week must be selected",
            str(context.exception),
            "ValidationError should mention that at " "least one day must be selected.",
        )

        # Try to update an existing task to have no days selected
        task = self.ScheduledTask.create(
            {
                "name": "Test DOW Task",
                "action": "command",
                "command_id": self.command_list_dir.id,
                "interval_type": "dow",
                "monday": True,
                "server_ids": [(6, 0, [self.server_test_1.id])],
            }
        )
        with self.assertRaises(ValidationError):
            task.write(
                {
                    "monday": False,
                    "tuesday": False,
                    "wednesday": False,
                    "thursday": False,
                    "friday": False,
                    "saturday": False,
                    "sunday": False,
                }
            )

    def test_get_next_call_dow_single_day_monday(self):
        """Test _get_next_call_dow edge case: only Monday selected,
        current day is Monday.
        Should wrap to next week's Monday."""
        # Create task with only Monday selected
        task = self.ScheduledTask.create(
            {
                "name": "Test DOW Task Single Day",
                "action": "command",
                "command_id": self.command_list_dir.id,
                "interval_type": "dow",
                "monday": True,
                "server_ids": [(6, 0, [self.server_test_1.id])],
            }
        )

        # Create a Monday datetime (2024-01-01 is a Monday)
        # Set time to 09:00:00
        monday_date = datetime(2024, 1, 1, 9, 0, 0)

        # Calculate next call
        next_call = task._get_next_call_dow(task, monday_date)

        # Should be Monday next week (7 days ahead) at the same time
        expected_next_monday = datetime(2024, 1, 8, 9, 0, 0)
        self.assertEqual(
            next_call,
            expected_next_monday,
            "Next call from Monday (only day selected) should be"
            " next Monday at the same time.",
        )

    def test_scheduled_task_cv_manager_read_access(self):
        """Manager: can read scheduled task CV if in scheduled task's
        manager_ids/user_ids or via server's manager_ids/user_ids."""
        # Test access via scheduled task manager_ids
        self.command_scheduled_task.manager_ids = [(6, 0, [self.manager.id])]
        cvs = self.ScheduledTaskCv.with_user(self.manager).search(
            [("id", "=", self.scheduled_task_cv_os.id)]
        )
        self.assertIn(
            self.scheduled_task_cv_os,
            cvs,
            "Manager should be able to read CV via scheduled task manager_ids.",
        )

        # Test access via scheduled task user_ids
        self.command_scheduled_task.manager_ids = [(5, 0, 0)]
        self.command_scheduled_task.user_ids = [(6, 0, [self.manager.id])]
        cvs = self.ScheduledTaskCv.with_user(self.manager).search(
            [("id", "=", self.scheduled_task_cv_os.id)]
        )
        self.assertIn(
            self.scheduled_task_cv_os,
            cvs,
            "Manager should be able to read CV via scheduled task user_ids.",
        )

        # Test access via server manager_ids
        self.command_scheduled_task.user_ids = [(5, 0, 0)]
        self.server_test_1.manager_ids = [(6, 0, [self.manager.id])]
        cvs = self.ScheduledTaskCv.with_user(self.manager).search(
            [("id", "=", self.scheduled_task_cv_os.id)]
        )
        self.assertIn(
            self.scheduled_task_cv_os,
            cvs,
            "Manager should be able to read CV via server manager_ids.",
        )

        # Test access via server user_ids
        self.server_test_1.manager_ids = [(5, 0, 0)]
        self.server_test_1.user_ids = [(6, 0, [self.manager.id])]
        cvs = self.ScheduledTaskCv.with_user(self.manager).search(
            [("id", "=", self.scheduled_task_cv_os.id)]
        )
        self.assertIn(
            self.scheduled_task_cv_os,
            cvs,
            "Manager should be able to read CV via server user_ids.",
        )

        # Remove manager from everywhere
        self.server_test_1.user_ids = [(5, 0, 0)]
        cvs = self.ScheduledTaskCv.with_user(self.manager).search(
            [("id", "=", self.scheduled_task_cv_os.id)]
        )
        self.assertNotIn(
            self.scheduled_task_cv_os,
            cvs,
            "Manager should NOT be able to read CV without relation.",
        )

    def test_scheduled_task_cv_manager_read_access_via_jet(self):
        """Manager: can read scheduled task CV if in jet's user_ids/manager_ids."""
        # Create CV for jet scheduled task
        jet_cv = self.ScheduledTaskCv.create(
            {
                "scheduled_task_id": self.jet_scheduled_task.id,
                "variable_id": self.variable_os.id,
                "value_char": "Linux",
            }
        )

        # Test access via jet manager_ids
        self.jet_test_access.manager_ids = [(6, 0, [self.manager.id])]
        cvs = self.ScheduledTaskCv.with_user(self.manager).search(
            [("id", "=", jet_cv.id)]
        )
        self.assertIn(
            jet_cv,
            cvs,
            "Manager should be able to read CV via jet manager_ids.",
        )

        # Test access via jet user_ids
        self.jet_test_access.manager_ids = [(5, 0, 0)]
        self.jet_test_access.user_ids = [(6, 0, [self.manager.id])]
        cvs = self.ScheduledTaskCv.with_user(self.manager).search(
            [("id", "=", jet_cv.id)]
        )
        self.assertIn(
            jet_cv,
            cvs,
            "Manager should be able to read CV via jet user_ids.",
        )

        # Test access via jet_template manager_ids
        self.jet_test_access.user_ids = [(5, 0, 0)]
        self.jet_template_test_access.manager_ids = [(6, 0, [self.manager.id])]
        cvs = self.ScheduledTaskCv.with_user(self.manager).search(
            [("id", "=", jet_cv.id)]
        )
        self.assertIn(
            jet_cv,
            cvs,
            "Manager should be able to read CV via jet_template manager_ids.",
        )

        # Test access via jet_template user_ids
        self.jet_template_test_access.manager_ids = [(5, 0, 0)]
        self.jet_template_test_access.user_ids = [(6, 0, [self.manager.id])]
        cvs = self.ScheduledTaskCv.with_user(self.manager).search(
            [("id", "=", jet_cv.id)]
        )
        self.assertIn(
            jet_cv,
            cvs,
            "Manager should be able to read CV via jet_template user_ids.",
        )

        # Remove manager from everywhere
        self._clear_all_access(
            self.jet_scheduled_task,
            jet=self.jet_test_access,
            jet_template=self.jet_template_test_access,
            server=self.server_test_1,
        )
        cvs = self.ScheduledTaskCv.with_user(self.manager).search(
            [("id", "=", jet_cv.id)]
        )
        self.assertNotIn(
            jet_cv,
            cvs,
            "Manager should NOT be able to read CV without relation.",
        )

    def test_scheduled_task_cv_manager_read_access_via_server_template(self):
        """Manager: can read scheduled task CV if in server_template's
        user_ids/manager_ids."""
        # Create scheduled task with server template
        server_template_task = self.ScheduledTask.create(
            {
                "name": "Test Server Template Scheduled Task for CV",
                "action": "command",
                "command_id": self.command_list_dir.id,
                "interval_number": 1,
                "interval_type": "days",
                "next_call": fields.Datetime.now(),
                "server_template_ids": [(6, 0, [self.server_template_sample.id])],
            }
        )
        server_template_cv = self.ScheduledTaskCv.create(
            {
                "scheduled_task_id": server_template_task.id,
                "variable_id": self.variable_os.id,
                "value_char": "Debian",
            }
        )

        # Test access via server_template manager_ids
        self.server_template_sample.manager_ids = [(6, 0, [self.manager.id])]
        cvs = self.ScheduledTaskCv.with_user(self.manager).search(
            [("id", "=", server_template_cv.id)]
        )
        self.assertIn(
            server_template_cv,
            cvs,
            "Manager should be able to read CV via server_template manager_ids.",
        )

        # Test access via server_template user_ids
        self.server_template_sample.manager_ids = [(5, 0, 0)]
        self.server_template_sample.user_ids = [(6, 0, [self.manager.id])]
        cvs = self.ScheduledTaskCv.with_user(self.manager).search(
            [("id", "=", server_template_cv.id)]
        )
        self.assertIn(
            server_template_cv,
            cvs,
            "Manager should be able to read CV via server_template user_ids.",
        )

        # Remove manager from everywhere
        self._clear_all_access(
            server_template_task,
            server_template=self.server_template_sample,
            server=self.server_test_1,
        )
        cvs = self.ScheduledTaskCv.with_user(self.manager).search(
            [("id", "=", server_template_cv.id)]
        )
        self.assertNotIn(
            server_template_cv,
            cvs,
            "Manager should NOT be able to read CV without relation.",
        )

    def test_scheduled_task_cv_manager_write_create_access(self):
        """Manager: can create/write CV if in scheduled task's manager_ids."""
        # Create CV as manager
        self.command_scheduled_task.manager_ids = [(6, 0, [self.manager.id])]
        cv = self.ScheduledTaskCv.with_user(self.manager).create(
            {
                "scheduled_task_id": self.command_scheduled_task.id,
                "variable_id": self.variable_os.id,
                "value_char": "Ubuntu",
            }
        )
        try:
            cv.with_user(self.manager).write({"value_char": "Fedora"})
        except AccessError:
            self.fail(
                "Manager should be able to write CV if in scheduled task manager_ids."
            )

        # Should fail if not in manager_ids
        self.command_scheduled_task.manager_ids = [(5, 0, 0)]
        with self.assertRaises(AccessError):
            self.scheduled_task_cv_os.with_user(self.manager).write(
                {"value_char": "CentOS"}
            )

    def test_scheduled_task_cv_manager_unlink_access(self):
        """Manager: can unlink CV only if in scheduled task's manager_ids & creator."""
        # Create CV as manager
        self.command_scheduled_task.manager_ids = [(6, 0, [self.manager.id])]
        cv = self.ScheduledTaskCv.with_user(self.manager).create(
            {
                "scheduled_task_id": self.command_scheduled_task.id,
                "variable_id": self.variable_os.id,
                "value_char": "Arch",
            }
        )
        try:
            cv.with_user(self.manager).unlink()
        except AccessError:
            self.fail("Manager should be able to unlink CV they created.")

        # Not creator
        self.command_scheduled_task.manager_ids = [(6, 0, [self.manager.id])]
        with self.assertRaises(AccessError):
            self.scheduled_task_cv_os.with_user(self.manager).unlink()

    def test_scheduled_task_cv_root_unrestricted_access(self):
        """Root: full unrestricted access to all scheduled task CVs."""
        # Read
        cvs = self.ScheduledTaskCv.with_user(self.root).search(
            [("id", "=", self.scheduled_task_cv_os.id)]
        )
        self.assertIn(
            self.scheduled_task_cv_os,
            cvs,
            "Root should be able to read any CV.",
        )

        # Create
        cv = self.ScheduledTaskCv.with_user(self.root).create(
            {
                "scheduled_task_id": self.command_scheduled_task.id,
                "variable_id": self.variable_os.id,
                "value_char": "SUSE",
            }
        )
        try:
            cv.with_user(self.root).write({"value_char": "OpenSUSE"})
            cv.with_user(self.root).unlink()
        except AccessError:
            self.fail("Root should be able to write/unlink any scheduled task CV.")
