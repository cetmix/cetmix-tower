# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from unittest.mock import patch

from odoo import _, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tools.misc import mute_logger

from ..models.constants import (
    ANOTHER_PLAN_RUNNING,
    GENERAL_ERROR,
    PLAN_IS_EMPTY,
    PLAN_LINE_CONDITION_CHECK_FAILED,
    PLAN_NOT_COMPATIBLE_WITH_SERVER,
    PLAN_STOPPED,
)
from .common import TestTowerCommon


class TestTowerPlan(TestTowerCommon):
    """Test the cx.tower.plan model."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Commands
        cls.command_run_flight_plan_1 = cls.Command.create(
            {
                "name": "Run Flight Plan",
                "action": "plan",
                "flight_plan_id": cls.plan_1.id,
            }
        )
        cls.command_python_custom_variable_values_1 = cls.Command.create(
            {
                "name": "Python command to set custom variable values",
                "action": "python_code",
                "code": """
custom_values['test_path_'] = '/test_path'
custom_values['test_dir'] = 'test_dir'
custom_values['_my_value'] = 'Just To Test'
""",
            }
        )
        cls.command_python_custom_variable_values_2 = cls.Command.create(
            {
                "name": "Python command to update custom variable values",
                "action": "python_code",
                "code": f"""
custom_values['test_path_'] = '/another_test_path'
custom_values['random_var_reference'] = 'random_var_value'
custom_values['{cls.variable_url.reference}'] = 'https://www.cetmix.com'
""",
            }
        )
        # Flight plan
        cls.plan_2 = cls.Plan.create(
            {
                "name": "Test plan 2",
                "note": "Run another flight plan",
            }
        )
        cls.plan_2_line_1 = cls.plan_line.create(
            {
                "sequence": 5,
                "plan_id": cls.plan_2.id,
                "command_id": cls.command_run_flight_plan_1.id,
            }
        )
        cls.plan_2_line_2 = cls.plan_line.create(
            {
                "sequence": 10,
                "command_id": cls.command_create_dir.id,
            }
        )
        # Flight plan with access level 1 to test user access rights
        cls.plan_3 = cls.Plan.create(
            {
                "name": "Test plan 3",
                "note": "Test user access rights",
                "access_level": "1",
                "line_ids": [
                    (0, 0, {"command_id": cls.command_create_dir.id, "sequence": 1}),
                ],
            }
        )
        # Create line for plan 3
        cls.plan_3_line_1 = cls.plan_line.create(
            {
                "plan_id": cls.plan_3.id,
                "command_id": cls.command_create_dir.id,
                "sequence": 10,
            }
        )
        cls.plan_3_line_1_action = cls.env["cx.tower.plan.line.action"].create(
            {
                "line_id": cls.plan_3_line_1.id,
                "condition": "==",
                "value_char": "test",
                "action": "e",
            }
        )
        cls.variable_value = cls.env["cx.tower.variable.value"].create(
            {
                "variable_id": cls.variable_os.id,
                "value_char": "Windows 2k",
                "plan_line_action_id": cls.plan_3_line_1_action.id,
            }
        )
        cls.server = cls.Server.create(
            {
                "name": "Plan Test Server",
                "ssh_username": "test",
                "ssh_password": "test",
                "ip_v4_address": "localhost",
                "ssh_port": 22,
                "user_ids": [(6, 0, [cls.user.id])],
                "manager_ids": [(6, 0, [cls.manager.id])],
                "skip_host_key": True,
            }
        )

    def _create_plan(self, **kwargs):
        """Helper method to create a flight plan."""
        vals = {
            "name": "Test Flight Plan",
            "access_level": "1",  # override default for user tests
            "user_ids": [(6, 0, [])],
            "manager_ids": [(6, 0, [])],
            "server_ids": [(6, 0, [])],
        }
        if kwargs:
            vals.update(kwargs)
        return self.Plan.create(vals)

    def test_user_read_access(self):
        """
        For a user:
          Read access is allowed if access_level == "1" and
          either the plan's own user_ids includes the user
          OR at least one related server (via server_ids)
          includes the user in its user_ids.
        """
        # Case 1: Plan with access_level "1" and user
        # included in plan.user_ids.
        plan1 = self._create_plan(
            **{
                "access_level": "1",
                "user_ids": [(6, 0, [self.user.id])],
            }
        )
        recs1 = self.Plan.with_user(self.user).search([("id", "=", plan1.id)])
        self.assertIn(
            plan1,
            recs1,
            "User should see the plan if in " "plan.user_ids and access_level == '1'.",
        )

        # Case 2: Plan with access_level "1" with no direct user_ids,
        # but with a related server that grants access.
        plan2 = self._create_plan(
            **{
                "access_level": "1",
                "user_ids": [(6, 0, [])],
                "server_ids": [(6, 0, [self.server.id])],
            }
        )
        recs2 = self.Plan.with_user(self.user).search([("id", "=", plan2.id)])
        self.assertIn(
            plan2,
            recs2,
            "User should see the plan if a "
            "related server.user_ids includes the user.",
        )

        # Negative: Plan with access_level "1"
        # with neither direct nor server-based access.
        plan3 = self._create_plan(
            **{
                "access_level": "1",
                "user_ids": [(6, 0, [])],
                "server_ids": [(6, 0, [])],
            }
        )
        recs3 = self.Plan.with_user(self.user).search([("id", "=", plan3.id)])
        self.assertNotIn(
            plan3,
            recs3,
            "User should not see the plan if not granted access.",
        )

        # Also, a user should not be allowed to create a plan.
        with self.assertRaises(AccessError):
            self.Plan.with_user(self.user).create(
                {
                    "name": "Test Plan",
                    "access_level": "1",
                    "user_ids": [(6, 0, [self.user.id])],
                }
            )
        # ...and modify a plan that they have access to.
        with self.assertRaises(AccessError):
            plan1.with_user(self.user).write({"name": "User Updated Plan"})

    def test_manager_read_access(self):
        """
        For a manager:
          Read access is allowed if access_level <= "2" AND
          EITHER the plan itself grants access
          (its user_ids or manager_ids includes the manager)
          OR either there are no related servers OR a related server
          grants access (its user_ids or manager_ids includes the manager).
        """
        # Case 1: Plan with access_level "2" and plan.manager_ids
        # includes the manager.
        plan1 = self._create_plan(
            **{
                "access_level": "2",
                "manager_ids": [(6, 0, [self.manager.id])],
            }
        )
        recs1 = self.Plan.with_user(self.manager).search([("id", "=", plan1.id)])
        self.assertIn(
            plan1,
            recs1,
            "Manager should see the plan if in "
            "plan.manager_ids and access_level <= '2'.",
        )

        # Case 2: Plan with access_level "2" that does not grant direct access,
        # but a related server grants access via its manager_ids.
        plan2 = self._create_plan(
            **{
                "access_level": "2",
                "user_ids": [(6, 0, [])],
                "manager_ids": [(6, 0, [])],
                "server_ids": [(6, 0, [self.server.id])],
            }
        )
        recs2 = self.Plan.with_user(self.manager).search([("id", "=", plan2.id)])
        self.assertIn(
            plan2,
            recs2,
            "Manager should see the plan if related "
            "server.manager_ids includes the manager.",
        )

        # Case 3 negative: Plan with access_level "2" with no granted access
        # if it's linked to a server that does not grant access.
        plan3 = self._create_plan(
            **{
                "access_level": "2",
                "user_ids": [(6, 0, [])],
                "manager_ids": [(6, 0, [])],
                "server_ids": [(6, 0, [self.server_test_1.id])],
            }
        )
        recs3 = self.Plan.with_user(self.manager).search([("id", "=", plan3.id)])
        self.assertNotIn(
            plan3,
            recs3,
            "Manager should not see the plan "
            "if not granted access to related server.",
        )

        # Case 4 positive: Plan with access_level "2" with no linked servers
        # and no related servers that grant access.
        plan4 = self._create_plan(
            **{
                "access_level": "2",
                "user_ids": [(6, 0, [])],
                "manager_ids": [(6, 0, [])],
                "server_ids": [(6, 0, [])],
            }
        )
        recs4 = self.Plan.with_user(self.manager).search([("id", "=", plan4.id)])
        self.assertIn(
            plan4,
            recs4,
            "Manager should see the plan if not linked to any servers.",
        )

        # Case 5 negative: raise access level to 3
        # and check if manager can see the plan
        plan4.access_level = "3"
        recs5 = self.Plan.with_user(self.manager).search([("id", "=", plan4.id)])
        self.assertNotIn(
            plan4,
            recs5,
            "Manager should not see the plan " "if access level is raised to 3.",
        )

    def test_manager_write_create_access(self):
        """
        For a manager:
          Write (update) and create access are allowed if access_level <= "2" AND
          the plan's own manager_ids includes the manager.
        """
        # Case 1: Plan with access_level "2" and plan.manager_ids
        #  includes the manager should allow to update the plan.
        plan1 = self._create_plan(
            **{
                "access_level": "2",
                "manager_ids": [(6, 0, [self.manager.id])],
            }
        )
        try:
            plan1.with_user(self.manager).write({"name": "Manager Updated Plan"})
        except AccessError:
            self.fail(
                "Manager should be able to update the plan if " "in plan.manager_ids.",
            )
        self.assertEqual(
            plan1.with_user(self.manager).name,
            "Manager Updated Plan",
        )

        # Case 2: Attempt to create a plan as a manager without
        #  including their ID in manager_ids should fail.
        with self.assertRaises(AccessError):
            self.Plan.with_user(self.manager).create(
                {
                    "name": "Manager Created Plan",
                    "access_level": "2",
                    "manager_ids": [(6, 0, [])],
                }
            )

        # Case 3: Create a plan with manager added to manager_ids
        # should be allowed.
        try:
            self.Plan.with_user(self.manager).create(
                {
                    "name": "Manager Created Plan",
                    "access_level": "2",
                    "manager_ids": [(6, 0, [self.manager.id])],
                }
            )
        except AccessError:
            self.fail(
                "Manager should be able to create a plan "
                "with himself added to manager_ids.",
            )

    def test_manager_unlink_access(self):
        """
        For a manager:
          Unlink (delete) access is allowed if access_level <= "2",
          the current user is the record creator,
          AND the plan's own manager_ids includes the manager.
        """
        # Scenario 1: Plan created by the manager with plan.manager_ids
        # including the manager.
        plan1 = self.Plan.with_user(self.manager).create(
            {
                "name": "Manager Created Plan",
                "access_level": "2",
            }
        )
        try:
            plan1.unlink()
        except AccessError:
            self.fail(
                "Manager should be able to delete the plan "
                "they created if in plan.manager_ids.",
            )

        # Scenario 2: Plan created by another user, even if
        # plan.manager_ids includes the manager.
        plan2 = self._create_plan(
            **{
                "access_level": "2",
                "manager_ids": [(6, 0, [self.manager.id])],
            }
        )
        with self.assertRaises(AccessError):
            plan2.with_user(self.manager).unlink()

    def test_root_unrestricted_access(self):
        """
        For a root user:
          Unlimited access: root can read, write, create, and delete plans
           regardless of access_level or related servers.
        """
        plan = self._create_plan(
            **{
                "access_level": "3",  # above threshold for managers
            }
        )
        recs = self.Plan.with_user(self.root).search([("id", "=", plan.id)])
        self.assertIn(
            plan,
            recs,
            "Root should see the plan regardless of restrictions.",
        )
        try:
            plan.with_user(self.root).write({"name": "Root Updated Plan"})
        except AccessError:
            self.fail("Root should be able to update the plan without restrictions.")
        self.assertEqual(plan.with_user(self.root).name, "Root Updated Plan")
        plan2 = self.Plan.with_user(self.root).create(
            {
                "name": "Root Created Plan",
                "access_level": "3",
            }
        )
        self.assertTrue(
            plan2,
            "Root should be able to create a plan without restrictions.",
        )
        plan2.with_user(self.root).unlink()
        recs_after = self.Plan.with_user(self.root).search([("id", "=", plan2.id)])
        self.assertFalse(
            recs_after,
            "Root should be able to delete the plan without restrictions.",
        )

    def test_plan_line_action_name(self):
        """Test plan line action naming"""

        # Add new line
        plan_line_1 = self.plan_line.create(
            {
                "plan_id": self.plan_1.id,
                "command_id": self.command_create_dir.id,
                "sequence": 10,
            }
        )

        # Add new action with custom
        action_1 = self.plan_line_action.create(
            {
                "line_id": plan_line_1.id,
                "condition": "==",
                "value_char": "35",
                "action": "e",
            }
        )

        # Check if action name is composed correctly
        expected_action_string = _(
            "If exit code == 35 then Exit with command exit code"
        )
        self.assertEqual(
            action_1.name,
            expected_action_string,
            msg="Action name doesn't match expected one",
        )

    def test_plan_get_next_action_values(self):
        """Test _get_next_action_values()

        NB: This test relies on demo data and might fail if it is modified
        """
        # Ensure demo date integrity just in case demo date is modified
        self.assertEqual(
            self.plan_1.line_ids[0].action_ids[1].custom_exit_code,
            255,
            "Plan 1 line #1 action #2 custom exit code must be equal to 255",
        )

        # Create a new plan log.
        plan_line_1 = self.plan_1.line_ids[0]  # Using command 1 from Plan 1
        plan_log = self.PlanLog.create(
            {
                "server_id": self.server_test_1.id,
                "plan_id": self.plan_1.id,
                "is_running": True,
                "start_date": fields.Datetime.now(),
                "plan_line_executed_id": plan_line_1.id,
            }
        )

        # ************************
        # Test with exit code == 0
        # Must run the next command
        # ************************
        command_log = self.CommandLog.create(
            {
                "plan_log_id": plan_log.id,
                "server_id": self.server_test_1.id,
                "command_id": plan_line_1.command_id.id,
                "command_response": "Ok",
                "command_status": 0,  # Error code
            }
        )
        action, exit_code, next_line_id = self.plan_1._get_next_action_values(
            command_log
        )
        self.assertEqual(action, "n", msg="Action must be 'Run next action'")
        self.assertEqual(exit_code, 0, msg="Exit code must be equal to 0")
        self.assertEqual(
            next_line_id,
            self.plan_line_2,
            msg="Next line must be Line #2",
        )

        # ************************
        # Test with exit code == 8
        # Must exit with custom code
        # ************************
        command_log.command_status = 8

        action, exit_code, next_line_id = self.plan_1._get_next_action_values(
            command_log
        )
        self.assertEqual(action, "ec", msg="Action must be 'Exit with custom code'")
        self.assertEqual(exit_code, 255, msg="Exit code must be equal to 255")
        self.assertIsNone(next_line_id, msg="Next line must be None")

        # ************************
        # Test with exit code == -12
        # Plan on error action must be triggered because no action condition is matched
        # ************************
        command_log.command_status = -12

        action, exit_code, next_line_id = self.plan_1._get_next_action_values(
            command_log
        )
        self.assertEqual(action, "e", msg="Action must be 'Exit with command code'")
        self.assertEqual(exit_code, -12, msg="Exit code must be equal to -12")
        self.assertIsNone(next_line_id, msg="Next line must be None")

        # ************************
        # Change Plan 'On error action' of the plan to 'Run next command'
        # Next line must be Line #2
        # ************************

        command_log.command_status = -12
        self.plan_1.on_error_action = "n"

        action, exit_code, next_line_id = self.plan_1._get_next_action_values(
            command_log
        )
        self.assertEqual(action, "n", msg="Action must be 'Run next action'")
        self.assertEqual(exit_code, -12, msg="Exit code must be equal to -12")
        self.assertEqual(
            next_line_id,
            self.plan_line_2,
            msg="Next line must be Line #2",
        )

        # ************************
        # Run Line 2 (the last one).
        # Action 2 will be triggered which is "Run next line".
        # However because this is the last line of the plan must exit with command code.
        # ************************

        plan_line_2 = self.plan_1.line_ids[1]
        plan_log.plan_line_executed_id = plan_line_2.id
        command_log.command_status = 3

        action, exit_code, next_line_id = self.plan_1._get_next_action_values(
            command_log
        )
        self.assertEqual(action, "e", msg="Action must be 'Exit with command code'")
        self.assertEqual(exit_code, 3, msg="Exit code must be equal to 3")
        self.assertIsNone(next_line_id, msg="Next line must be None")

        # ************************
        # Run Line 2 (the last one).
        # Fallback plan action must be triggered because no action condition is matched
        # However because this is the last line of the plan must exit with command code.
        # ************************

        command_log.command_status = 1

        action, exit_code, next_line_id = self.plan_1._get_next_action_values(
            command_log
        )
        self.assertEqual(action, "e", msg="Action must be 'Exit with command code'")
        self.assertEqual(exit_code, 1, msg="Exit code must be equal to 1")
        self.assertIsNone(next_line_id, msg="Next line must be None")

    def test_plan_run_single(self):
        """Test plan execution results"""

        # Add user as user to Server1
        self.server_test_1.user_ids = [(4, self.user_bob.id)]

        # Ensure that access error is raised
        # Because user_bob is not in any Tower group
        with self.assertRaises(AccessError):
            self.plan_1.with_user(self.user_bob)._run_single(self.server_test_1)

        # Add user to the "User" group
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")

        # Ensure that access error is raised
        # Because plan access level is "Manager" and user_bob is in "User" group
        with self.assertRaises(AccessError):
            self.plan_1.with_user(self.user_bob)._run_single(self.server_test_1)

        # Set access level to 1 and link to server1
        # so Bob can execute the plan
        self.write_and_invalidate(
            self.plan_1,
            **{"access_level": "1", "server_ids": [(4, self.server_test_1.id)]},
        )

        self.env["ir.rule"].invalidate_model()
        # Run plan
        self.plan_1.with_user(self.user_bob)._run_single(self.server_test_1)

        # Check plan log
        plan_log_rec = self.PlanLog.search([("server_id", "=", self.server_test_1.id)])

        # Must be a single record
        self.assertEqual(len(plan_log_rec), 1, msg="Must be a single plan record")

        # Ensure all commands were triggered
        expected_command_count = 2
        self.assertEqual(
            len(plan_log_rec.command_log_ids),
            expected_command_count,
            msg=f"Must run {expected_command_count} commands",
        )

        # Check plan status
        expected_plan_status = 0
        self.assertEqual(
            plan_log_rec.plan_status,
            expected_plan_status,
            msg=f"Plan status must be equal to {expected_plan_status}",
        )

        # ************************
        # Change condition in line #1.
        # Action 1 will be triggered which is "Exit with custom code" 29.
        # ************************
        action_to_tweak = self.plan_line_1_action_1
        action_to_tweak.write({"custom_exit_code": 29, "action": "ec"})

        # Run plan
        self.plan_1._run_single(self.server_test_1)

        # Check plan log
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )

        # Must be two plan log record
        self.assertEqual(len(plan_log_records), 2, msg="Must be 2 plan log records")
        plan_log_rec = plan_log_records[0]

        # Ensure all commands were triggered
        expected_command_count = 1
        self.assertEqual(
            len(plan_log_rec.command_log_ids),
            expected_command_count,
            msg=f"Must run {expected_command_count} commands",
        )

        # Check plan status
        expected_plan_status = 29
        self.assertEqual(
            plan_log_rec.plan_status,
            expected_plan_status,
            msg=f"Plan status must be equal to {expected_plan_status}",
        )

        # Ensure 'path' was substituted with the plan line custom 'path'
        self.assertEqual(
            self.plan_line_1.path,
            plan_log_rec.command_log_ids.path,
            "Path in command log must be the same as in the flight plan line",
        )

    def test_plan_and_command_access_level(self):
        # Remove userbob from all cxtower_server groups
        self.remove_from_group(
            self.user_bob,
            [
                "cetmix_tower_server.group_user",
                "cetmix_tower_server.group_manager",
                "cetmix_tower_server.group_root",
            ],
        )

        # Add user_bob to group_manager
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")

        # Add user_bob as manager to the plan
        self.plan_1.manager_ids = [(4, self.user_bob.id)]

        # check if plan and commands included has same access level
        self.assertEqual(self.plan_1.access_level, "2")
        self.assertEqual(self.command_create_dir.access_level, "2")
        self.assertEqual(self.command_list_dir.access_level, "2")

        # check that if we modify plan access level to make it lower than the
        # access_level of the commands related with it access level,
        # access_level_warn_msg will be created
        self.plan_1.with_user(self.user_bob).write({"access_level": "1"})
        self.assertTrue(self.plan_1.access_level_warn_msg)

        # Add user_bob to group_root
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_root")

        # check if user_bob can make plan access leve higher than commands access level
        self.plan_1.with_user(self.user_bob).write({"access_level": "3"})
        self.assertEqual(self.plan_1.access_level, "3")

        # check that if we create a new plan with an access_level lower than
        # the access_level of the command related with access_level_warn_msg
        #  will be created
        command_1 = self.Command.create(
            {"name": "New Test Command", "access_level": "3"}
        )

        self.plan_2 = self.Plan.create(
            {
                "name": "Test plan 2",
                "note": "Create directory and list its content",
            }
        )
        self.plan_line_2_1 = self.plan_line.create(
            {
                "sequence": 5,
                "plan_id": self.plan_2.id,
                "command_id": command_1.id,
            }
        )
        self.assertTrue(self.plan_2.access_level_warn_msg)

    def test_multiple_plan_create_write(self):
        """Test multiple plan create/write cases"""
        # Create multiple plans at once
        plans_data = [
            {
                "name": "Test Plan 1",
                "note": "Plan 1 Note",
                "tag_ids": [(6, 0, [self.tag_test_staging.id])],
            },
            {
                "name": "Test Plan 2",
                "note": "Plan 2 Note",
                "tag_ids": [(6, 0, [self.tag_test_production.id])],
            },
            {
                "name": "Test Plan 3",
                "note": "Plan 3 Note",
                "tag_ids": [(6, 0, [self.tag_test_staging.id])],
            },
        ]
        created_plans = self.Plan.create(plans_data)
        # Check that all plans are created successfully
        self.assertTrue(all(created_plans))
        # Update the access level of the created plans
        created_plans.write({"access_level": "3"})
        # Check that all plans are updated successfully
        self.assertTrue(all(plan.access_level == "3" for plan in created_plans))

    def test_plan_with_first_not_executable_condition(self):
        """
        Test plan with not executable condition for first plan line
        """
        # Add condition for the first plan line
        self.plan_line_1.condition = "{{ odoo_version }} == '14.0'"
        # Run plan
        self.plan_1._run_single(self.server_test_1)
        # Check plan log
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        self.assertEqual(
            len(plan_log_records.command_log_ids),
            2,
            msg="Must be two command records",
        )
        self.assertTrue(
            plan_log_records.command_log_ids[0].is_skipped,
            msg="First command must be skipped",
        )
        self.assertFalse(
            plan_log_records.command_log_ids[1].is_skipped,
            msg="Second command not must be skipped",
        )

    def test_plan_with_second_not_executable_condition(self):
        """
        Test plan with not executable condition for second plan line
        """
        # Add condition for second plan line
        self.plan_line_2.condition = "{{ odoo_version }} == '14.0'"
        # Run plan
        self.plan_1._run_single(self.server_test_1)
        # Check plan log
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        self.assertEqual(
            len(plan_log_records.command_log_ids),
            2,
            msg="Must be two command records",
        )
        self.assertTrue(
            plan_log_records.command_log_ids[1].is_skipped,
            msg="Second command must be skipped",
        )
        self.assertFalse(
            plan_log_records.command_log_ids[0].is_skipped,
            msg="First command not must be skipped",
        )

    def test_plan_with_executable_condition(self):
        """
        Test plan with executable condition for plan line
        """
        # Add condition for first plan line
        self.plan_line_1.condition = "1 == 1"
        # Create a global value for the 'Version' variable
        self.VariableValue.create(
            {"variable_id": self.variable_version.id, "value_char": "14.0"}
        )
        # Add condition with variable
        self.plan_line_2.condition = (
            "{{ " + self.variable_version.name + " }} == '14.0'"
        )
        # Run plan
        self.plan_1._run_single(self.server_test_1)
        # Check commands
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        self.assertEqual(
            len(plan_log_records.command_log_ids),
            2,
            msg="Must be two command records",
        )
        self.assertTrue(
            all(not command.is_skipped for command in plan_log_records.command_log_ids),
            msg="All command should be executed",
        )

    def test_plan_with_update_variables(self):
        """
        Test plan updates custom (in-flight) values
        """
        # Add new variable to server
        self.VariableValue.create(
            {
                "variable_id": self.variable_version.id,
                "value_char": "14.0",
                "server_id": self.server_test_1.id,
            }
        )
        # Create new variable value on action
        self.VariableValue.create(
            {
                "variable_id": self.variable_version.id,
                "value_char": "16.0",
                "plan_line_action_id": self.plan_line_1_action_1.id,
            }
        )
        # Add a new variable value on action for a variable absent on the server
        self.VariableValue.create(
            {
                "variable_id": self.variable_os.id,
                "value_char": "Ubuntu",
                "plan_line_action_id": self.plan_line_1_action_1.id,
            }
        )
        # Pre-run sanity: server holds initial value and no OS value
        exist_server_values = self.server_test_1.variable_value_ids.filtered(
            lambda rec: rec.variable_id == self.variable_version
        )
        self.assertEqual(
            len(exist_server_values),
            1,
            "The server should have only one value for the variable",
        )
        self.assertEqual(
            exist_server_values.value_char,
            "14.0",
            "The server variable value should be '14.0'",
        )
        exist_server_values = self.server_test_1.variable_value_ids.filtered(
            lambda rec: rec.variable_id == self.variable_os
        )
        self.assertFalse(
            exist_server_values, "The server should not have this variable"
        )
        # Run plan
        self.plan_1._run_single(self.server_test_1)
        # After run: server values MUST remain unchanged
        server_version_val = self.server_test_1.variable_value_ids.filtered(
            lambda rec: rec.variable_id == self.variable_version
        )
        self.assertEqual(
            server_version_val.value_char,
            "14.0",
            "Server variable value must remain unchanged",
        )
        self.assertFalse(
            self.server_test_1.variable_value_ids.filtered(
                lambda rec: rec.variable_id == self.variable_os
            ),
            "Server must not receive new variable from action",
        )

        # But custom (in-flight) values MUST be updated in logs
        plan_log = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)], order="id desc", limit=1
        )
        self.assertTrue(plan_log, "Plan log should exist after run")
        self.assertEqual(
            plan_log.variable_values[self.variable_version.reference],
            "16.0",
            "Plan log must contain updated custom value",
        )
        self.assertEqual(
            plan_log.variable_values[self.variable_os.reference],
            "Ubuntu",
            "Plan log must contain new custom value",
        )

        last_command_log = plan_log.command_log_ids and plan_log.command_log_ids[-1]
        self.assertTrue(last_command_log, "Command log should exist after run")
        self.assertEqual(
            last_command_log.variable_values[self.variable_version.reference],
            "16.0",
            "Command log must contain updated custom value",
        )

    def test_plan_with_action_variables_for_condition(self):
        """
        Test plan with update server variables and use new
        value as condition for next plan line
        """
        # Add new variable to server
        self.VariableValue.create(
            {
                "variable_id": self.variable_version.id,
                "value_char": "14.0",
                "server_id": self.server_test_1.id,
            }
        )
        # Create new variable value to action to update existing server variable
        self.VariableValue.create(
            {
                "variable_id": self.variable_version.id,
                "value_char": "16.0",
                "plan_line_action_id": self.plan_line_1_action_1.id,
            }
        )
        # Add condition with variable
        self.plan_line_2.condition = (
            "{{ " + self.variable_version.name + " }} == '14.0'"
        )
        # Run plan
        self.plan_1._run_single(self.server_test_1)
        # Check commands
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        # The second line of the plan should be skipped because the
        # first line of the plan updated the value of the variable
        self.assertTrue(
            plan_log_records.command_log_ids[1].is_skipped,
            msg="Second command must be skipped",
        )

        # Change condition for plan line
        self.plan_line_2.condition = (
            "{{ " + self.variable_version.name + " }} == '16.0'"
        )
        # Run plan
        self.plan_1._run_single(self.server_test_1)
        # Check commands
        new_plan_log_records = (
            self.PlanLog.search([("server_id", "=", self.server_test_1.id)])
            - plan_log_records
        )
        # The second line of the plan should be skipped because the
        # first line of the plan updated the value of the variable
        self.assertFalse(
            new_plan_log_records.command_log_ids[1].is_skipped,
            msg="The second plan line should not be skipped",
        )

    def test_flight_plan_copy(self):
        """Test duplicating a Flight Plan with lines, actions, and variable values"""

        # Create a Flight Plan
        plan = self.Plan.create(
            {
                "name": "Test Flight Plan",
                "note": "Test Note",
            }
        )

        # Create a command for the plan line
        command = self.Command.create(
            {
                "name": "Test Command",
                # Command to get Linux kernel version
                "code": "uname -r",
            }
        )

        # Create a Flight Plan Line
        plan_line = self.plan_line.create(
            {
                "plan_id": plan.id,
                "command_id": command.id,
                "path": "/test/path",
                # Condition based on Linux version
                "condition": '{{ test_linux_version }} >= "5.0"',
            }
        )

        # Create a variable for the action
        variable = self.Variable.create({"name": "test_linux_version"})

        # Create an Action for the Plan Line
        action = self.plan_line_action.create(
            {
                "line_id": plan_line.id,
                "action": "n",  # next action
                "condition": "==",
                "value_char": "0",  # condition for success
            }
        )

        # Create a Variable Value for the Action
        self.env["cx.tower.variable.value"].create(
            {
                "variable_id": variable.id,
                "value_char": "5.0",
                "plan_line_action_id": action.id,
            }
        )

        # Duplicate the Flight Plan
        copied_plan = plan.copy()

        # Ensure the new Flight Plan was created with a new ID
        self.assertNotEqual(
            copied_plan.id,
            plan.id,
            "Copied plan should have a different ID from the original",
        )

        # Check that the copied plan has the same number of lines
        self.assertEqual(
            len(copied_plan.line_ids),
            len(plan.line_ids),
            "Copied plan should have the same number of lines as the original",
        )

        # Check that the copied plan's lines have the same actions as the original
        original_line = plan.line_ids
        copied_line = copied_plan.line_ids

        # Ensure the command, condition, and custom path are copied correctly
        self.assertEqual(
            copied_line.command_id.id,
            original_line.command_id.id,
            "Command should be the same in copied line",
        )
        self.assertEqual(
            copied_line.path,
            original_line.path,
            "Custom path should be the same in copied line",
        )
        self.assertEqual(
            copied_line.condition,
            original_line.condition,
            "Condition should be the same in copied line",
        )

        # Ensure actions were copied correctly
        self.assertEqual(
            len(copied_line.action_ids),
            len(original_line.action_ids),
            "Number of actions should be the same in the copied line",
        )
        self.assertEqual(
            copied_line.action_ids.action,
            original_line.action_ids.action,
            "Action should be the same in the copied line",
        )
        self.assertEqual(
            copied_line.action_ids.condition,
            original_line.action_ids.condition,
            "Action condition should be the same in the copied line",
        )
        self.assertEqual(
            copied_line.action_ids.value_char,
            original_line.action_ids.value_char,
            "Action value should be the same in the copied line",
        )

        # Check that variable values were copied correctly
        original_action = original_line.action_ids
        copied_action = copied_line.action_ids

        self.assertEqual(
            len(copied_action.variable_value_ids),
            len(original_action.variable_value_ids),
            "Number of variable values should be the same in the copied action",
        )

        self.assertEqual(
            copied_action.variable_value_ids.variable_id.id,
            original_action.variable_value_ids.variable_id.id,
            "Variable should be the same in the copied action",
        )
        self.assertEqual(
            copied_action.variable_value_ids.value_char,
            original_action.variable_value_ids.value_char,
            "Variable value should be the same in the copied action",
        )

    def test_plan_with_another_plan(self):
        """
        Test to check running another plan from current plan
        """
        # Check plan logs
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        self.assertEqual(len(plan_log_records), 0, "Plan logs should be empty")
        # Run plan
        self.plan_2._run_single(self.server_test_1)
        # Check plan logs after execute command with plan action
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        self.assertEqual(len(plan_log_records), 2, msg="Should be 2 plan logs")

        parent_plan_log = plan_log_records.filtered(
            lambda rec: rec.plan_id == self.plan_2
        )
        self.assertTrue(parent_plan_log, "The log for Plan 2 must exist!")
        self.assertEqual(
            parent_plan_log.plan_status, 0, "Plan log should success status"
        )

        child_plan_log = plan_log_records - parent_plan_log
        self.assertEqual(
            child_plan_log.parent_flight_plan_log_id,
            parent_plan_log,
            "Second plan log should contain parent log link",
        )
        self.assertEqual(
            child_plan_log.plan_status,
            parent_plan_log.command_log_ids.command_status,
            "The command status of main plan should be equal "
            "of status second flight plan",
        )
        self.assertEqual(
            parent_plan_log.command_log_ids.triggered_plan_log_id,
            child_plan_log,
            "The command triggered plan line should be equal to child plan",
        )

        # Check that we cannot add recursive plan
        with self.assertRaisesRegex(
            ValidationError, "Recursive plan call detected in plan.*"
        ):
            self.plan_line.create(
                {
                    "sequence": 20,
                    "plan_id": self.plan_1.id,
                    "command_id": self.command_run_flight_plan_1.id,
                }
            )

        # Delete plan lines from first plan
        self.plan_1.line_ids = False
        # Run plan
        self.plan_2._run_single(self.server_test_1)
        plan_log_records = (
            self.PlanLog.search([("server_id", "=", self.server_test_1.id)])
            - plan_log_records
        )

        parent_plan_log = plan_log_records.filtered(
            lambda rec: rec.plan_id == self.plan_2
        )
        self.assertTrue(parent_plan_log, "The log for Plan 2 must exist!")
        self.assertEqual(
            parent_plan_log.plan_status, PLAN_IS_EMPTY, "Plan log should failed status"
        )

        child_plan_log = plan_log_records - parent_plan_log
        self.assertEqual(
            child_plan_log.parent_flight_plan_log_id,
            parent_plan_log,
            "Second plan log should contain parent log link",
        )
        self.assertEqual(
            child_plan_log.plan_status,
            parent_plan_log.command_log_ids.command_status,
            "The command status of parent plan should be equal "
            "of status second flight plan",
        )

    def test_plan_with_two_plans(self):
        """
        Test to check two plans from plan
        """
        self.plan_line.create(
            {
                "sequence": 15,
                "plan_id": self.plan_2.id,
                "command_id": self.command_run_flight_plan_1.id,
            }
        )
        # Check plan logs
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        self.assertEqual(len(plan_log_records), 0, "Plan logs should be empty")
        # Run plan
        self.plan_2._run_single(self.server_test_1)
        # Check plan logs after execute command with plan action
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        self.assertEqual(len(plan_log_records), 3, msg="Should be 3 plan logs")

    def test_plan_with_nested_plans(self):
        """
        Test to check two plans from plan
        """
        command_run_flight_plan_2 = self.Command.create(
            {
                "name": "Run Flight Plan",
                "action": "plan",
                "flight_plan_id": self.plan_2.id,
            }
        )
        plan_3 = self.Plan.create(
            {
                "name": "Test plan 3",
                "note": "Run flight plan 2",
            }
        )
        self.plan_line.create(
            {
                "sequence": 5,
                "plan_id": plan_3.id,
                "command_id": command_run_flight_plan_2.id,
            }
        )
        # Check plan logs
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        self.assertEqual(len(plan_log_records), 0, "Plan logs should be empty")
        # Run plan
        plan_3._run_single(self.server_test_1)
        # Check plan logs after execute command with plan action
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        self.assertEqual(len(plan_log_records), 3, msg="Should be 3 plan logs")

        last_child_plan_log = plan_log_records.filtered(
            lambda rec: rec.plan_id == self.plan_1
        )
        self.assertTrue(last_child_plan_log, "The log for Plan 1 must exist!")
        self.assertEqual(
            last_child_plan_log.plan_status, 0, "Plan log should success status"
        )

        self.assertIn(
            last_child_plan_log.parent_flight_plan_log_id,
            plan_log_records,
            "Parent plan logs should exist",
        )
        self.assertEqual(
            last_child_plan_log.parent_flight_plan_log_id.plan_id,
            self.plan_2,
            "Parent plan should be equal to plan 2",
        )

        child_plan_log = plan_log_records.filtered(
            lambda rec: rec.plan_id == self.plan_2
        )
        self.assertIn(
            child_plan_log.parent_flight_plan_log_id,
            plan_log_records,
            "Parent plan logs should exist",
        )
        self.assertEqual(
            child_plan_log.parent_flight_plan_log_id.plan_id,
            plan_3,
            "Parent plan should be equal to plan 3",
        )
        self.assertEqual(
            child_plan_log.command_log_ids.triggered_plan_log_id,
            last_child_plan_log,
            "The command triggered plan line should be equal to last child plan",
        )
        self.assertEqual(
            child_plan_log.command_log_ids.triggered_plan_log_id,
            last_child_plan_log,
            "The command triggered plan line should be equal to last child plan",
        )
        parent_plan_log = plan_log_records - child_plan_log - last_child_plan_log
        self.assertEqual(
            parent_plan_log.command_log_ids.triggered_plan_log_id,
            child_plan_log,
            "The command triggered plan line from parent plan "
            "should be equal to child plan",
        )

        # Check that we cannot change command with existing plan,
        # because it's recursive plan
        with self.assertRaisesRegex(
            ValidationError, "Recursive plan call detected in plan.*"
        ):
            self.plan_line_1.write(
                {
                    "command_id": command_run_flight_plan_2.id,
                }
            )

        # Set the previous command back

        self.plan_line_1.write(
            {
                "command_id": self.command_create_dir.id,
            }
        )
        # --- Check server dependency handling

        # Remove all existing flight plan logs
        self.PlanLog.search([]).unlink()

        # Set server dependency for plan 2
        self.plan_2.write(
            {
                "server_ids": [(6, 0, [self.server.id])],
            }
        )
        plan_log = self.server_test_1.run_flight_plan(self.plan_2)
        self.assertEqual(plan_log.plan_status, PLAN_NOT_COMPATIBLE_WITH_SERVER)

        # Run plan on allowed server
        plan_log = self.server.run_flight_plan(self.plan_2)
        self.assertEqual(plan_log.plan_status, 0)

    def test_failed_first_child_plan_with_another_plan(self):
        """
        Check that child plan was failed then parent plan is failed too
        """
        # Add new plan line
        self.plan_line.create(
            {
                "sequence": 15,
                "plan_id": self.plan_2.id,
                "command_id": self.command_run_flight_plan_1.id,
            }
        )
        # Check plan logs
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        self.assertEqual(len(plan_log_records), 0, "Plan logs should be empty")

        # Simulate a failed Plan 1. To achieve this, we need to update the command
        # associated with Plan 1 to apply the desired side effect.
        self.plan_1.line_ids.command_id[0].code = "fail"

        # Run plan
        self.plan_2._run_single(self.server_test_1)

        # Check plan logs after execute command with plan action
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        # 2 logs only because plan should exist with error after first failed command
        self.assertEqual(len(plan_log_records), 2, msg="Should be 2 plan logs")

        parent_plan_log = plan_log_records.filtered(
            lambda rec: rec.plan_id == self.plan_2
        )
        self.assertTrue(parent_plan_log, "The log for Plan 2 must exist!")
        self.assertEqual(
            parent_plan_log.plan_status, GENERAL_ERROR, "Plan log should failed status"
        )

        child_plan_log = plan_log_records - parent_plan_log
        self.assertEqual(
            child_plan_log.parent_flight_plan_log_id,
            parent_plan_log,
            "Second plan log should contain parent log link",
        )
        self.assertEqual(
            child_plan_log.plan_status,
            parent_plan_log.command_log_ids.command_status,
            "The command status of main plan should be equal "
            "of status second flight plan",
        )

    def test_failed_second_child_plan_with_another_plan(self):
        """
        Check that child plan was failed then parent plan is failed too
        """
        # Add new plan line
        line = self.plan_line.create(
            {
                "sequence": 15,
                "plan_id": self.plan_2.id,
                "command_id": self.command_run_flight_plan_1.id,
            }
        )

        cx_tower_plan_obj = self.registry["cx.tower.plan"]
        _run_single_super = cx_tower_plan_obj._run_single

        def _run_single(this, *args, **kwargs):
            if (
                this == self.plan_1
                and this.env["cx.tower.plan.log"]
                .browse(kwargs["log"]["plan_log_id"])
                .plan_line_executed_id
                == line
            ):
                # Simulate a failed Plan 1. To achieve this, we need to update
                # the command associated with Plan 1 to apply the desired side effect.
                self.plan_1.line_ids.command_id[0].code = "fail"
            return _run_single_super(this, *args, **kwargs)

        with patch.object(cx_tower_plan_obj, "_run_single", _run_single):
            # Run plan
            self.plan_2._run_single(self.server_test_1)

        # Check plan logs after execute command with plan action
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        # 3 logs because plan should exist with error after second failed command
        self.assertEqual(len(plan_log_records), 3, msg="Should be 3 plan logs")

        parent_plan_log = plan_log_records.filtered(
            lambda rec: rec.plan_id == self.plan_2
        )
        self.assertTrue(parent_plan_log, "The log for Plan 2 must exist!")
        self.assertEqual(
            parent_plan_log.plan_status, GENERAL_ERROR, "Plan log should failed status"
        )

        child_plan_log = plan_log_records - parent_plan_log
        self.assertEqual(
            child_plan_log.parent_flight_plan_log_id,
            parent_plan_log,
            "Second plan log should contain parent log link",
        )
        self.assertEqual(
            len(child_plan_log),
            2,
            "Must be 2 child plan logs",
        )
        self.assertIn(
            GENERAL_ERROR,
            child_plan_log.mapped("plan_status"),
            "One of plan status of child plan must be GENERAL_ERROR",
        )
        self.assertIn(
            0,
            child_plan_log.mapped("plan_status"),
            "One of plan status of child plan must be GENERAL_ERROR",
        )

    def test_plan_with_another_plan_with_condition(self):
        """
        Test that parent plan will success finished
        if child plan executable by condition
        """
        # Add condition for first plan line
        self.plan_line_1.condition = "1 == 1"
        # Check plan logs
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        self.assertEqual(len(plan_log_records), 0, "Plan logs should be empty")
        # Run plan
        self.plan_2._run_single(self.server_test_1)
        # Check plan logs after execute command with plan action
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )

        self.assertEqual(len(plan_log_records), 2, msg="Should be 2 plan logs")

        parent_plan_log = plan_log_records.filtered(
            lambda rec: rec.plan_id == self.plan_2
        )
        self.assertTrue(parent_plan_log, "The log for Plan 2 must exist!")
        self.assertEqual(
            parent_plan_log.plan_status, 0, "Plan log should success status"
        )

        child_plan_log = plan_log_records - parent_plan_log
        self.assertEqual(
            child_plan_log.parent_flight_plan_log_id,
            parent_plan_log,
            "Second plan log should contain parent log link",
        )
        self.assertEqual(
            child_plan_log.plan_status,
            parent_plan_log.command_log_ids.command_status,
            "The command status of main plan should be equal "
            "of status second flight plan",
        )

    def test_plan_with_another_plan_with_not_executable_condition(self):
        """
        Test plan with not executable condition for second plan line
        """
        # Add condition for first plan line
        self.plan_line_1.condition = "{{ odoo_version }} == '14.0'"
        # Check plan logs
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )
        self.assertEqual(len(plan_log_records), 0, "Plan logs should be empty")
        # Run plan
        self.plan_2._run_single(self.server_test_1)

        # Check plan logs after execute command with plan action
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )

        self.assertEqual(len(plan_log_records), 2, msg="Should be 2 plan logs")

        self.assertIn(
            PLAN_LINE_CONDITION_CHECK_FAILED,
            plan_log_records.command_log_ids.mapped("command_status"),
            "One of commands should be skipped",
        )

    def test_plan_with_another_plan_with_all_not_executable_condition(self):
        """
        Test plan with not executable condition for second plan line
        """
        # Add condition for all plan lines
        self.plan_line_1.condition = "{{ odoo_version }} == '14.0'"
        self.plan_line_2.condition = "{{ odoo_version }} == '14.0'"

        self.plan_2_line_1.condition = "{{ odoo_version }} == '14.0'"
        self.plan_2_line_2.condition = "{{ odoo_version }} == '14.0'"

        self.plan_2._run_single(self.server_test_1)

        # Check plan logs after execute command with plan action
        plan_log_records = self.PlanLog.search(
            [("server_id", "=", self.server_test_1.id)]
        )

        self.assertEqual(len(plan_log_records), 1, msg="Should be 1 plan logs")
        self.assertEqual(
            PLAN_LINE_CONDITION_CHECK_FAILED,
            plan_log_records.command_log_ids.command_status,
            "Command status should be skipped",
        )

    def test_plan_unlink(self):
        plan = self.plan_1.copy()
        plan_id = plan.id
        plan_line_ids = plan.line_ids
        plan_line_action_ids = plan.mapped("line_ids.action_ids")

        plan.unlink()

        self.assertFalse(
            self.Plan.search([("id", "=", plan_id)]), msg="Plan should be deleted"
        )
        self.assertFalse(
            self.plan_line.search([("id", "in", plan_line_ids.ids)]),
            msg="Plan line should be deleted when Plan is deleted",
        )
        self.assertFalse(
            self.plan_line_action.search([("id", "in", plan_line_action_ids.ids)]),
            msg="Plan line action should be deleted when Plan line is deleted",
        )

    def test_plan_command_server_compatibility(self):
        """Test plan execution with server-restricted flight plans"""
        # Create a new test server
        test_server = self.Server.create(
            {
                "name": "Test Server",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "host_key": "test_key",
            }
        )

        # Create a flight plan restricted to the test server
        plan = self.Plan.create(
            {
                "name": "Server Restricted Plan",
                "server_ids": [(6, 0, [test_server.id])],
                "line_ids": [
                    (0, 0, {"command_id": self.command_create_dir.id, "sequence": 1})
                ],
            }
        )

        # Should fail when executing on non-allowed server
        plan_log = plan._run_single(self.server_test_1)
        self.assertEqual(plan_log.plan_status, PLAN_NOT_COMPATIBLE_WITH_SERVER)

        # Should work on allowed server
        plan._run_single(test_server)
        plan_log = self.PlanLog.search(
            [("plan_id", "=", plan.id), ("server_id", "=", test_server.id)], limit=1
        )
        self.assertEqual(plan_log.command_log_ids.command_status, 0)

    def test_another_plan_running(self):
        """Test the parallel plan running"""

        # Ensure that the plan doesn't allow parallel running
        self.plan_1.write({"allow_parallel_run": False})

        # Create a new plan log with a plan that is already running
        self.PlanLog.create(
            {
                "plan_id": self.plan_1.id,
                "server_id": self.server_test_1.id,
                "start_date": fields.Datetime.now(),
            }
        )

        # Launch the same plan on the same server
        plan_log = self.server_test_1.run_flight_plan(self.plan_1)
        self.assertEqual(plan_log.plan_status, ANOTHER_PLAN_RUNNING)

        # Now allow parallel running
        self.plan_1.write({"allow_parallel_run": True})

        # Launch the same plan on the same server
        plan_log = self.server_test_1.run_flight_plan(self.plan_1)
        self.assertEqual(plan_log.plan_status, 0)

    def test_plan_custom_variables(self):
        """Test plan with custom variables"""
        command_python_1_id = self.command_python_custom_variable_values_1.id
        command_python_2_id = self.command_python_custom_variable_values_2.id

        plan = self._create_plan(
            **{
                "name": "Plan with custom variables",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "command_id": command_python_1_id,
                            "sequence": 1,
                        },
                    ),
                    (0, 0, {"command_id": self.command_create_dir.id, "sequence": 2}),
                    (
                        0,
                        0,
                        {
                            "command_id": command_python_2_id,
                            "sequence": 3,
                        },
                    ),
                    (0, 0, {"command_id": self.command_create_dir.id, "sequence": 4}),
                ],
            }
        )

        # Run plan
        plan_log = self.server_test_1.run_flight_plan(plan)

        # Check that custom variable values were updated correctly
        # (The log of plan should contain the last updatedvalues)
        self.assertEqual(plan_log.variable_values["test_path_"], "/another_test_path")
        self.assertEqual(plan_log.variable_values["test_dir"], "test_dir")
        self.assertEqual(
            plan_log.variable_values["random_var_reference"], "random_var_value"
        )
        self.assertEqual(plan_log.variable_values["_my_value"], "Just To Test")

        command_logs = plan_log.command_log_ids
        self.assertEqual(
            len(command_logs),
            len(plan.line_ids),
            f"Should be {len(plan.line_ids)} command logs.",
        )

        # Check that custom variable values were created correctly
        # in first python command log
        command_python_command_1_log = command_logs.filtered(
            lambda log: log.command_id.id == command_python_1_id
        )
        self.assertEqual(
            command_python_command_1_log.variable_values["test_path_"], "/test_path"
        )
        self.assertEqual(
            command_python_command_1_log.variable_values["test_dir"], "test_dir"
        )
        self.assertEqual(
            command_python_command_1_log.variable_values["_my_value"], "Just To Test"
        )

        # Check that custom variable values used in rendered command code
        command_create_dir_logs = command_logs.filtered(
            lambda log: log.command_id == self.command_create_dir
        )
        first_command_create_dir_log = command_create_dir_logs[0]
        second_command_create_dir_log = command_create_dir_logs[1]

        # the first_command_create_dir_log.code is equal to
        # 'cd /test_path && mkdir test_dir'
        # because rendered code contains custom variable values updated
        # from first python command
        self.assertEqual(
            first_command_create_dir_log.code, "cd /test_path && mkdir test_dir"
        )

        # Check that custom variable values were updated correctly in command logs
        command_python_command_2_log = command_logs.filtered(
            lambda log: log.command_id.id == command_python_2_id
        )
        self.assertEqual(
            command_python_command_2_log.variable_values["test_path_"],
            "/another_test_path",
        )
        self.assertEqual(
            command_python_command_2_log.variable_values["test_dir"], "test_dir"
        )
        self.assertEqual(
            command_python_command_2_log.variable_values["random_var_reference"],
            "random_var_value",
        )
        self.assertEqual(
            command_python_command_2_log.variable_values["_my_value"], "Just To Test"
        )
        self.assertEqual(
            command_python_command_2_log.variable_values[self.variable_url.reference],
            "https://www.cetmix.com",
        )

        # the second_command_create_dir_log.code is equal to
        # 'cd /another_test_path && mkdir test_dir'
        # because rendered code contains custom variable values updated
        # from second python command
        self.assertEqual(
            second_command_create_dir_log.code,
            "cd /another_test_path && mkdir test_dir",
        )

    def test_plan_custom_variables_wizard(self):
        """Test plan with custom variables from wizard"""
        command_python_1_id = self.command_python_custom_variable_values_1.id
        command_python_2_id = self.command_python_custom_variable_values_2.id
        plan = self._create_plan(
            **{
                "name": "Plan with custom variables",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "command_id": command_python_1_id,
                            "sequence": 1,
                        },
                    ),
                    (0, 0, {"command_id": self.command_create_dir.id, "sequence": 2}),
                    (
                        0,
                        0,
                        {
                            "command_id": command_python_2_id,
                            "sequence": 3,
                        },
                    ),
                    (0, 0, {"command_id": self.command_create_dir.id, "sequence": 4}),
                ],
            }
        )

        # Create wizard with custom variable values
        wizard = self.env["cx.tower.plan.run.wizard"].create(
            {
                "plan_id": plan.id,
                "server_ids": [(6, 0, [self.server_test_1.id])],
                "custom_variable_value_ids": [
                    (
                        0,
                        0,
                        {
                            "variable_id": self.variable_version.id,
                            "value_char": "16.0",
                        },
                    ),
                ],
            }
        )

        # Run wizard
        action = wizard.run_flight_plan()
        plan_log = self.PlanLog.search(
            [("label", "=", action["context"]["search_default_label"])],
            limit=1,
        )
        self.assertTrue(plan_log, "Plan log should be created")

        # Check that custom variable values were updated correctly
        # (The log of plan should contain the last updated
        # values + custom variable value from wizard)
        self.assertEqual(plan_log.variable_values["test_path_"], "/another_test_path")
        self.assertEqual(plan_log.variable_values["test_dir"], "test_dir")
        self.assertEqual(
            plan_log.variable_values["random_var_reference"], "random_var_value"
        )
        self.assertEqual(plan_log.variable_values["_my_value"], "Just To Test")
        self.assertEqual(
            plan_log.variable_values[self.variable_version.reference], "16.0"
        )

    def test_plan_with_another_plan_custom_variables(self):
        """Test plan with another plan with custom variables"""
        # Create plan with next structure:
        # Plan 1:
        # - Command 1: Run plan 2
        # - Command 2: Run Python command to set custom variable values
        # - Command 3: Create directory
        # Plan 2:
        # - Command 1: Python command to set custom variable values
        # - Command 2: Create directory
        # - Command 3: Python command to update custom variable values

        command_python_1_id = self.command_python_custom_variable_values_1.id
        command_python_2_id = self.command_python_custom_variable_values_2.id
        plan2 = self._create_plan(
            **{
                "name": "Plan 2",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "command_id": command_python_1_id,
                            "sequence": 1,
                        },
                    ),
                    (0, 0, {"command_id": self.command_create_dir.id, "sequence": 2}),
                    (
                        0,
                        0,
                        {
                            "command_id": command_python_2_id,
                            "sequence": 3,
                        },
                    ),
                ],
            }
        )

        command_run_plan_2 = self.Command.create(
            {
                "name": "Run Flight Plan",
                "action": "plan",
                "flight_plan_id": plan2.id,
            }
        )
        command_python_custom_variable_values_3 = self.Command.create(
            {
                "name": "Python command to update custom variable values",
                "action": "python_code",
                "code": """
custom_values['random_var_reference'] = 'another_random_var_value'
""",
            }
        )

        plan1 = self._create_plan(
            **{
                "name": "Plan 1",
                "line_ids": [
                    (0, 0, {"command_id": command_run_plan_2.id, "sequence": 1}),
                    (
                        0,
                        0,
                        {
                            "command_id": command_python_custom_variable_values_3.id,
                            "sequence": 2,
                        },
                    ),
                    (0, 0, {"command_id": self.command_create_dir.id, "sequence": 3}),
                ],
            }
        )

        # Create wizard with custom variable values
        wizard = self.env["cx.tower.plan.run.wizard"].create(
            {
                "plan_id": plan1.id,
                "server_ids": [(6, 0, [self.server_test_1.id])],
                "custom_variable_value_ids": [
                    (
                        0,
                        0,
                        {
                            "variable_id": self.variable_version.id,
                            "value_char": "16.0",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "variable_id": self.variable_url.id,
                            "value_char": "https://www.test.com",
                        },
                    ),
                ],
            }
        )

        # Run wizard
        action = wizard.run_flight_plan()
        plan_log = self.PlanLog.search(
            [("label", "=", action["context"]["search_default_label"])],
            limit=1,
        )
        self.assertTrue(plan_log, "Plan log should be created")

        command_logs = plan_log.command_log_ids
        self.assertEqual(
            len(command_logs),
            len(plan1.line_ids),
            f"Should be {len(plan1.line_ids)} command logs.",
        )

        # First command log is run plan 2 log that contains custom variable values
        # updated from plan 2. This command log should contain the same custom
        # variable values as from plan 2 log
        run_plan2_command_log = command_logs[0]
        run_plan2_command_log_variable_values = run_plan2_command_log.variable_values

        plan2_log = run_plan2_command_log.triggered_plan_log_id
        plan2_log_variable_values = plan2_log.variable_values

        # check that variable values are the same
        self.assertEqual(
            run_plan2_command_log_variable_values, plan2_log_variable_values
        )

        # Before finished command (run child plan): we have next variable values:
        # {'test_version': '16.0', 'test_url': 'https://www.test.com'}

        # After finished command (run child plan): we have next variable values:
        # {
        #     'test_version': '16.0',
        #     'test_url': 'https://www.cetmix.com',
        #     'test_path_': '/another_test_path',
        #     'test_dir': 'test_dir',
        #     '_my_value': 'Just To Test',
        #     'random_var_reference': 'random_var_value'
        # }
        self.assertEqual(
            run_plan2_command_log_variable_values["test_path_"], "/another_test_path"
        )
        self.assertEqual(run_plan2_command_log_variable_values["test_dir"], "test_dir")
        self.assertEqual(
            run_plan2_command_log_variable_values["_my_value"], "Just To Test"
        )
        self.assertEqual(
            run_plan2_command_log_variable_values["random_var_reference"],
            "random_var_value",
        )
        self.assertEqual(
            run_plan2_command_log_variable_values[self.variable_version.reference],
            "16.0",
        )
        self.assertEqual(
            run_plan2_command_log_variable_values[self.variable_url.reference],
            "https://www.cetmix.com",
        )

        # After finished main plan: we have next variable values:
        # {
        #     'test_version': '16.0',
        #     'test_url': 'https://www.cetmix.com',
        #     'test_path_': '/another_test_path',
        #     'test_dir': 'test_dir',
        #     '_my_value': 'Just To Test',
        #     'random_var_reference': 'another_random_var_value'
        # }
        self.assertEqual(plan_log.variable_values["test_path_"], "/another_test_path")
        self.assertEqual(plan_log.variable_values["test_dir"], "test_dir")
        self.assertEqual(plan_log.variable_values["_my_value"], "Just To Test")
        self.assertEqual(
            plan_log.variable_values["random_var_reference"], "another_random_var_value"
        )
        self.assertEqual(
            plan_log.variable_values[self.variable_version.reference], "16.0"
        )
        self.assertEqual(
            plan_log.variable_values[self.variable_url.reference],
            "https://www.cetmix.com",
        )

    def test_plan_with_custom_values_in_condition(self):
        """
        Ensure that plan line conditions see updated custom_values
        produced by previous commands.

        1) python sets test_path_ = '/test_path'
        2) create_dir with condition "{{ test_path_ }} == '/test_path'" -> executes
        3) python updates test_path_ = '/another_test_path'
        4) create_dir with condition "{{ test_path_ }} == '/another_test_path'"
           -> executes
        Then invert conditions and check both lines are skipped appropriately.
        """
        command_python_1_id = self.command_python_custom_variable_values_1.id
        command_python_2_id = self.command_python_custom_variable_values_2.id

        plan = self._create_plan(
            **{
                "name": "Plan with custom_values in condition",
                "line_ids": [
                    (0, 0, {"command_id": command_python_1_id, "sequence": 1}),
                    (
                        0,
                        0,
                        {
                            "command_id": self.command_create_dir.id,
                            "sequence": 2,
                            "condition": "{{ test_path_ }} == '/test_path'",
                        },
                    ),
                    (0, 0, {"command_id": command_python_2_id, "sequence": 3}),
                    (
                        0,
                        0,
                        {
                            "command_id": self.command_create_dir.id,
                            "sequence": 4,
                            "condition": "{{ test_path_ }} == '/another_test_path'",
                        },
                    ),
                ],
            }
        )

        plan_log = self.server_test_1.run_flight_plan(plan)

        logs = plan_log.command_log_ids
        self.assertEqual(len(logs), 4, "Should be 4 command logs")

        create_dir_logs = logs.filtered(
            lambda line: line.command_id == self.command_create_dir
        )
        self.assertEqual(len(create_dir_logs), 2, "Should be 2 create_dir logs")

        self.assertFalse(
            create_dir_logs[0].is_skipped, "First create_dir must be executed"
        )
        self.assertFalse(
            create_dir_logs[1].is_skipped, "Second create_dir must be executed"
        )

        self.assertIn("/test_path", create_dir_logs[0].code)
        self.assertIn("/another_test_path", create_dir_logs[1].code)

    def test_plan_stop_mid_execution(self):
        """
        Test that plan is correctly marked as stopped and
        further commands are not executed.
        """
        plan = self._create_plan(
            name="Test Plan Stop",
            line_ids=[
                (0, 0, {"command_id": self.command_create_dir.id, "sequence": 1}),
                (0, 0, {"command_id": self.command_list_dir.id, "sequence": 2}),
            ],
        )
        server = self.server_test_1

        cx_tower_plan_line_obj = self.registry["cx.tower.plan.line"]
        _run_super = cx_tower_plan_line_obj._run

        # Save plan_log for control is_running
        plan_log_holder = {}

        def fake_run(self, server, plan_log, **kwargs):
            # Save plan_log for control is_running
            plan_log_holder["log"] = plan_log

            # Call stop() after first command
            if len(plan_log.command_log_ids) == 0:
                plan_log.stop()
                # After this call plan_log should be stopped,
                # and finish_date should be filled
            # Continue execution in standard way
            return _run_super(self, server, plan_log, **kwargs)

        with patch.object(cx_tower_plan_line_obj, "_run", new=fake_run):
            plan_log = plan._run_single(server)

        self.assertTrue(plan_log.is_stopped, "Plan should be stopped")
        self.assertFalse(plan_log.is_running, "Plan should not be in running status")
        self.assertEqual(
            plan_log.plan_status, PLAN_STOPPED, "Status should be PLAN_STOPPED"
        )
        self.assertTrue(plan_log.finish_date, "Finish date should be filled")
        self.assertLessEqual(
            len(plan_log.command_log_ids),
            1,
            "There should be maximum one command in the log",
        )

    def test_flight_plan_reference_update(self):
        """Test flight plan reference update cascades to dependent models"""
        # 1. Add a variable value to plan_line_1_action_2
        variable_value = self.VariableValue.create(
            {
                "variable_id": self.variable_os.id,
                "value_char": "Ubuntu 20.04",
                "plan_line_action_id": self.plan_line_1_action_2.id,
            }
        )

        # Store original references for comparison
        original_plan_reference = self.plan_1.reference
        original_plan_line_1_reference = self.plan_line_1.reference
        original_plan_line_2_reference = self.plan_line_2.reference
        original_plan_line_1_action_1_reference = self.plan_line_1_action_1.reference
        original_plan_line_1_action_2_reference = self.plan_line_1_action_2.reference
        original_plan_line_2_action_1_reference = self.plan_line_2_action_1.reference
        original_plan_line_2_action_2_reference = self.plan_line_2_action_2.reference
        original_variable_value_reference = variable_value.reference

        # 2. Change the reference for plan_1 to "nice_new_plan"
        self.plan_1.write({"reference": "nice_new_plan"})

        # 3. Verify that references are updated for plan lines
        # Invalidate models to refresh all references
        self.env["cx.tower.plan"].invalidate_model(["reference"])
        self.env["cx.tower.plan.line"].invalidate_model(["reference"])
        self.env["cx.tower.plan.line.action"].invalidate_model(["reference"])
        self.env["cx.tower.variable.value"].invalidate_model(["reference"])

        # Check that plan reference was updated
        self.assertEqual(self.plan_1.reference, "nice_new_plan")
        self.assertNotEqual(self.plan_1.reference, original_plan_reference)

        # Check that plan line references were updated to include the new plan reference
        self.assertIn("nice_new_plan", self.plan_line_1.reference)
        self.assertIn("nice_new_plan", self.plan_line_2.reference)
        self.assertNotEqual(self.plan_line_1.reference, original_plan_line_1_reference)
        self.assertNotEqual(self.plan_line_2.reference, original_plan_line_2_reference)

        # Check that plan line action references were updated
        self.assertIn("nice_new_plan", self.plan_line_1_action_1.reference)
        self.assertIn("nice_new_plan", self.plan_line_1_action_2.reference)
        self.assertIn("nice_new_plan", self.plan_line_2_action_1.reference)
        self.assertIn("nice_new_plan", self.plan_line_2_action_2.reference)
        self.assertNotEqual(
            self.plan_line_1_action_1.reference, original_plan_line_1_action_1_reference
        )
        self.assertNotEqual(
            self.plan_line_1_action_2.reference, original_plan_line_1_action_2_reference
        )
        self.assertNotEqual(
            self.plan_line_2_action_1.reference, original_plan_line_2_action_1_reference
        )
        self.assertNotEqual(
            self.plan_line_2_action_2.reference, original_plan_line_2_action_2_reference
        )

        # Check that variable value reference was updated
        #  to include the new plan reference
        self.assertIn("nice_new_plan", variable_value.reference)
        self.assertNotEqual(variable_value.reference, original_variable_value_reference)

        # Verify the reference pattern for variable value follows the expected format:
        # <variable_reference>_<model_generic_reference>_<linked_model_generic_reference>_<linked_record_reference>  # noqa: E501
        expected_pattern = (
            f"{self.variable_os.reference}_variable_value_plan_line_action_"
            f"{self.plan_line_1_action_2.reference}"
        )
        self.assertEqual(variable_value.reference, expected_pattern)

    def test_flight_plan_with_child_plan_command_exception(self):
        """
        Test flight plan with child plan where command exception occurs.

        Scenario:
        - Main flight plan has 2 commands:
          1. Simple python command (success)
          2. Child flight plan with 2 commands where first fails with command exception
        - Verify error propagation: command -> child plan -> main plan
        - The command exception is simulated using the existing mocking system
         that raises exceptions when commands contain "raise"
        """

        # Create child flight plan with 2 commands
        child_plan = self.Plan.create(
            {
                "name": "Child Plan with Error",
                "note": "Child plan that will fail on first command",
            }
        )

        # Command 1 of child plan - will fail with command exception
        child_command_1 = self.Command.create(
            {
                "name": "Child Command 1 - Command Exception",
                "action": "ssh_command",
                "code": "raise",  # This will trigger command exception in mock
            }
        )

        # Command 2 of child plan - should not execute due to error in command 1
        child_command_2 = self.Command.create(
            {
                "name": "Child Command 2 - Should Not Run",
                "action": "python_code",
                "code": """
result = {
    "exit_code": 0,
    "message": "This should not execute"
}
            """,
            }
        )

        # Create plan lines for child plan
        self.plan_line.create(
            {
                "sequence": 10,
                "plan_id": child_plan.id,
                "command_id": child_command_1.id,
            }
        )
        self.plan_line.create(
            {
                "sequence": 20,
                "plan_id": child_plan.id,
                "command_id": child_command_2.id,
            }
        )

        # Create command to run child plan
        run_child_plan_command = self.Command.create(
            {
                "name": "Run Child Plan",
                "action": "plan",
                "flight_plan_id": child_plan.id,
            }
        )

        # Create main flight plan with 2 commands
        main_plan = self.Plan.create(
            {
                "name": "Main Plan with Child Plan",
                "note": "Main plan with python command and child plan",
            }
        )

        # Command 1 of main plan - simple python command (should succeed)
        main_command_1 = self.Command.create(
            {
                "name": "Main Command 1 - Python Success",
                "action": "python_code",
                "code": """
result = {
    "exit_code": 0,
    "message": "Main plan python command executed successfully"
}
            """,
            }
        )

        # Command 2 of main plan - run child plan (will fail)
        main_command_2 = run_child_plan_command

        # Create plan lines for main plan
        self.plan_line.create(
            {
                "sequence": 10,
                "plan_id": main_plan.id,
                "command_id": main_command_1.id,
            }
        )
        self.plan_line.create(
            {
                "sequence": 20,
                "plan_id": main_plan.id,
                "command_id": main_command_2.id,
            }
        )
        # Run the first command again
        self.plan_line.create(
            {
                "sequence": 30,
                "plan_id": main_plan.id,
                "command_id": main_command_1.id,
            }
        )

        # Run the main flight plan
        plan_log = self.server_test_1.run_flight_plan(main_plan)

        # Verify main plan finished with error
        self.assertNotEqual(
            plan_log.plan_status, 0, "Main plan should not finish successfully"
        )

        # Get all plan logs for verification
        all_plan_logs = plan_log | self.PlanLog.search(
            [("parent_flight_plan_log_id", "=", plan_log.id)]
        )

        # Should have 2 plan logs: main plan and child plan
        self.assertEqual(
            len(all_plan_logs), 2, "Should have 2 plan logs: main and child"
        )

        main_plan_log = all_plan_logs.filtered(lambda log: log.plan_id == main_plan)
        child_plan_log = all_plan_logs.filtered(
            lambda log: log.parent_flight_plan_log_id == main_plan_log
        )

        self.assertTrue(main_plan_log, "Main plan log should exist")
        self.assertTrue(child_plan_log, "Child plan log should exist")

        # Verify child plan finished with error
        # The child plan should finish with an error
        # (either SSH_CONNECTION_ERROR or GENERAL_ERROR)
        self.assertNotEqual(
            child_plan_log.plan_status,
            0,
            "Child plan should not finish successfully",
        )

        # Get command logs for verification
        all_command_logs = self.CommandLog.search(
            [("plan_log_id", "in", all_plan_logs.ids)]
        )

        # Should have 3 command logs: main python,
        # run child plan, child command exception
        self.assertEqual(len(all_command_logs), 3, "Should have 3 command logs")

        # Find specific command logs
        main_python_log = all_command_logs.filtered(
            lambda log: log.command_id == main_command_1
        )
        run_child_plan_log = all_command_logs.filtered(
            lambda log: log.command_id == main_command_2
        )
        child_ssh_error_log = all_command_logs.filtered(
            lambda log: log.command_id == child_command_1
        )

        # Verify main python command succeeded
        self.assertEqual(
            main_python_log.command_status, 0, "Main python command should succeed"
        )
        self.assertEqual(
            main_python_log.command_response,
            "Main plan python command executed successfully",
            "Main python command should have correct response",
        )

        # Verify run child plan command failed
        # The command should fail with an error
        # (either SSH_CONNECTION_ERROR or GENERAL_ERROR)
        self.assertNotEqual(
            run_child_plan_log.command_status,
            0,
            "Run child plan command should fail",
        )

        # Verify child SSH command failed
        # The SSH command should fail with an error status
        # (could be GENERAL_ERROR -100 or 255 depending on how the exception is handled)
        self.assertNotEqual(
            child_ssh_error_log.command_status, 0, "Child SSH command should fail"
        )
        # The error message should contain information about
        # the SSH connection failure
        # The exact error message may vary depending
        # on how the exception is handled
        self.assertTrue(
            child_ssh_error_log.command_error,
            "Child SSH command should have an error message",
        )

        # Verify that child command 2 was not executed (no log for it)
        child_command_2_log = all_command_logs.filtered(
            lambda log: log.command_id == child_command_2
        )
        self.assertFalse(
            child_command_2_log, "Child command 2 should not have been executed"
        )

        # Verify plan log relationships
        self.assertEqual(
            main_plan_log.command_log_ids,
            main_python_log | run_child_plan_log,
            "Main plan should have correct command logs",
        )

        self.assertEqual(
            child_plan_log.command_log_ids,
            child_ssh_error_log,
            "Child plan should have only the failed command log",
        )

        # Verify that the error propagated correctly through the hierarchy
        # The error should propagate from command -> child plan -> main plan
        # The specific error codes may vary depending
        # on how the system handles the error
        self.assertNotEqual(
            main_plan_log.plan_status,
            0,
            "Error should propagate from child to main plan",
        )
        self.assertNotEqual(
            child_plan_log.plan_status, 0, "Error should be present in child plan"
        )
        self.assertNotEqual(
            child_ssh_error_log.command_status,
            0,
            "SSH command should have an error status",
        )
        self.assertEqual(
            child_ssh_error_log.command_status,
            child_plan_log.plan_status,
            "Child plan should have the same error status as the SSH command",
        )
        self.assertEqual(
            child_ssh_error_log.command_status,
            main_plan_log.plan_status,
            "Main plan should have the same error status as the SSH command",
        )

    def test_skip_command_error_flow(self):
        """Plan flow:
        1) success, 2) success, 3) error -> sets command_error variable,
        4) skipped if not var, 5) runs if var and exits -1.
        """
        # Create commands
        command_success = self.Command.create(
            {
                "name": "Command -> Success",
                "action": "python_code",
                "code": "# Just return default values",
            }
        )
        command_error = self.Command.create(
            {
                "name": "Command -> Error",
                "action": "python_code",
                "code": "result = {'exit_code': -100, 'message': 'Error'}",
            }
        )
        command_after_failed = self.Command.create(
            {
                "name": "Command -> After failed",
                "action": "python_code",
                "code": (
                    "name = server.name + ' --after-failed-- '\n"
                    "server.write({'name': name})"
                ),
            }
        )
        command_last_one = self.Command.create(
            {
                "name": "Command -> The last one",
                "action": "python_code",
                "code": (
                    "name = server.name + ' --last-one-- '\n"
                    "server.write({'name': name})"
                ),
            }
        )

        # Variable used in conditions
        variable_command_error = self.Variable.create(
            {
                "name": "command_error",
                "reference": "test_command_error",
                "variable_type": "s",
            }
        )

        # Plan and lines
        plan = self.Plan.create(
            {
                "name": "Test skip command error",
                "on_error_action": "e",
                "custom_exit_code": 0,
            }
        )

        self.plan_line.create(
            {"sequence": 10, "plan_id": plan.id, "command_id": command_success.id}
        )
        self.plan_line.create(
            {"sequence": 20, "plan_id": plan.id, "command_id": command_success.id}
        )

        line3 = self.plan_line.create(
            {"sequence": 30, "plan_id": plan.id, "command_id": command_error.id}
        )
        action3 = self.plan_line_action.create(
            {
                "line_id": line3.id,
                "sequence": 10,
                "condition": "!=",
                "value_char": "0",
                "action": "n",
            }
        )

        self.VariableValue.create(
            {
                "variable_id": variable_command_error.id,
                "value_char": "1",
                "plan_line_action_id": action3.id,
            }
        )

        self.plan_line.create(
            {
                "sequence": 40,
                "plan_id": plan.id,
                "command_id": command_after_failed.id,
                "condition": "not {{ test_command_error }}",
                "variable_ids": [(6, 0, [variable_command_error.id])],
            }
        )

        line5 = self.plan_line.create(
            {
                "sequence": 50,
                "plan_id": plan.id,
                "command_id": command_last_one.id,
                "condition": "{{ test_command_error }}",
                "variable_ids": [(6, 0, [variable_command_error.id])],
            }
        )
        self.plan_line_action.create(
            {
                "line_id": line5.id,
                "sequence": 10,
                "condition": "==",
                "value_char": "0",
                "action": "ec",
                "custom_exit_code": -1,
            }
        )

        plan_log = self.server_test_1.run_flight_plan(plan)

        self.assertEqual(len(plan_log.command_log_ids), 5)
        logs = plan_log.command_log_ids
        self.assertTrue(
            all(
                log.command_status == 0
                for log in logs.filtered(lambda log: log.command_id == command_success)
            )
        )

        error_log = logs.filtered(lambda log: log.command_id == command_error)
        self.assertIn(variable_command_error.reference, error_log.variable_values)
        self.assertTrue(error_log.command_status == GENERAL_ERROR)

        self.assertTrue(
            logs.filtered(lambda log: log.command_id == command_after_failed).mapped(
                "command_status"
            )[0]
            == PLAN_LINE_CONDITION_CHECK_FAILED
        )
        self.assertTrue(
            logs.filtered(lambda log: log.command_id == command_last_one).mapped(
                "command_status"
            )[0]
            == 0
        )

        # Final plan status must be custom exit code -1 from line 5 action
        self.assertEqual(plan_log.plan_status, -1)

    def test_plan_line_condition_error(self):
        """Test plan line condition error
        First line is skipped because of condition error
        Second line is executed successfully
        """
        # Create commands
        command_success = self.Command.create(
            {
                "name": "Command -> Success",
                "action": "python_code",
                "code": "# Just return default values",
            }
        )

        # Plan and lines
        plan = self.Plan.create(
            {
                "name": "Test plan line condition error",
            }
        )

        self.plan_line.create(
            {
                "sequence": 10,
                "plan_id": plan.id,
                "command_id": command_success.id,
                "condition": "=q",
            },
        )
        self.plan_line.create(
            {"sequence": 20, "plan_id": plan.id, "command_id": command_success.id}
        )

        with mute_logger("odoo.addons.cetmix_tower_server.models.cx_tower_plan_line"):
            plan_log = self.server_test_1.run_flight_plan(plan)

        # Must be 2 command logs
        self.assertEqual(len(plan_log.command_log_ids), 2)
        logs = plan_log.command_log_ids
        self.assertTrue(logs[0].is_skipped)
        self.assertTrue(logs[1].command_status == 0)
