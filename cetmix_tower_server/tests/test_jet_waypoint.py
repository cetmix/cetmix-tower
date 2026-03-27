# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError
from odoo.tools import mute_logger

from .common_jets import TestTowerJetsCommon


class TestTowerJetWaypoint(TestTowerJetsCommon):
    """
    Test the Jet Waypoint model functionality
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create variables for testing
        cls.variable_test_1 = cls.Variable.create(
            {
                "name": "Test Variable 1",
                "reference": "test_var_1",
            }
        )
        cls.variable_test_2 = cls.Variable.create(
            {
                "name": "Test Variable 2",
                "reference": "test_var_2",
            }
        )
        cls.variable_test_3 = cls.Variable.create(
            {
                "name": "Test Variable 3",
                "reference": "test_var_3",
            }
        )
        # waypoint_template and waypoint are now inherited from TestTowerJetsCommon

        # Create commands for flight plans
        cls.command_success = cls.Command.create(
            {
                "name": "Command -> Success",
                "action": "python_code",
                "code": "# Just return default values",
            }
        )
        cls.command_error = cls.Command.create(
            {
                "name": "Command -> Error",
                "action": "python_code",
                "code": "result = {'exit_code': -100, 'message': 'Error'}",
            }
        )
        cls.command_waypoint_check = cls.Command.create(
            {
                "name": "Command -> Waypoint Check",
                "action": "python_code",
                "code": (
                    "result = {'exit_code': waypoint.id if waypoint else -1, "
                    "'message': 'waypoint check'}"
                ),
            }
        )

        # Create flight plans
        cls.plan_success = cls.Plan.create(
            {
                "name": "Waypoint Success Plan",
            }
        )
        cls.plan_line.create(
            {
                "sequence": 10,
                "plan_id": cls.plan_success.id,
                "command_id": cls.command_success.id,
            }
        )

        cls.plan_error = cls.Plan.create(
            {
                "name": "Waypoint Error Plan",
            }
        )
        cls.plan_line.create(
            {
                "sequence": 10,
                "plan_id": cls.plan_error.id,
                "command_id": cls.command_error.id,
            }
        )

        cls.plan_waypoint_check = cls.Plan.create(
            {
                "name": "Waypoint Check Plan",
            }
        )
        cls.plan_line.create(
            {
                "sequence": 10,
                "plan_id": cls.plan_waypoint_check.id,
                "command_id": cls.command_waypoint_check.id,
            }
        )

    def test_save_variable_values_empty(self):
        """
        Test _save_variable_values when jet has no variable values
        """
        # Ensure jet has no variable values
        self.jet_test.variable_value_ids.unlink()

        # Save variable values
        result = self.waypoint._save_variable_values()

        # Should return True
        self.assertTrue(result, "Should return True when saving values")

        # Waypoint should have empty variable_values (or False, which is equivalent)
        variable_values = self.waypoint.variable_values or {}
        self.assertEqual(
            variable_values,
            {},
            "Variable values should be empty dict when jet has no values",
        )

    def test_save_variable_values_with_values(self):
        """
        Test _save_variable_values when jet has variable values
        """
        # Create variable values for the jet
        self.VariableValue.create(
            {
                "variable_id": self.variable_test_1.id,
                "value_char": "value_1",
                "jet_id": self.jet_test.id,
            }
        )
        self.VariableValue.create(
            {
                "variable_id": self.variable_test_2.id,
                "value_char": "value_2",
                "jet_id": self.jet_test.id,
            }
        )

        # Save variable values
        result = self.waypoint._save_variable_values()

        # Should return True
        self.assertTrue(result, "Should return True when saving values")

        # Waypoint should have saved variable values
        self.assertEqual(
            self.waypoint.variable_values,
            {"test_var_1": "value_1", "test_var_2": "value_2"},
            "Variable values should be saved correctly",
        )

    def test_save_variable_values_with_empty_string(self):
        """
        Test _save_variable_values when variable value is empty string
        """
        # Create variable value with empty string
        self.VariableValue.create(
            {
                "variable_id": self.variable_test_1.id,
                "value_char": "",
                "jet_id": self.jet_test.id,
            }
        )

        # Save variable values
        self.waypoint._save_variable_values()

        # Waypoint should have saved empty string value
        self.assertEqual(
            self.waypoint.variable_values,
            {"test_var_1": ""},
            "Empty string values should be saved",
        )

    def test_save_variable_values_only_jet_values(self):
        """
        Test _save_variable_values only saves jet-specific values,
        not template/server/global values
        """
        # Create jet-specific variable value
        self.VariableValue.create(
            {
                "variable_id": self.variable_test_1.id,
                "value_char": "jet_value",
                "jet_id": self.jet_test.id,
            }
        )

        # Create template variable value (should not be saved)
        self.VariableValue.create(
            {
                "variable_id": self.variable_test_2.id,
                "value_char": "template_value",
                "jet_template_id": self.jet_template_test.id,
            }
        )

        # Save variable values
        self.waypoint._save_variable_values()

        # Waypoint should only have jet-specific value
        self.assertEqual(
            self.waypoint.variable_values,
            {"test_var_1": "jet_value"},
            "Should only save jet-specific values",
        )
        self.assertNotIn(
            "test_var_2",
            self.waypoint.variable_values,
            "Should not save template values",
        )

    def test_restore_variable_values_empty(self):
        """
        Test _restore_variable_values when waypoint has no saved values
        """
        # Create some variable values in jet
        self.VariableValue.create(
            {
                "variable_id": self.variable_test_1.id,
                "value_char": "existing_value",
                "jet_id": self.jet_test.id,
            }
        )

        # Set waypoint variable_values to empty
        self.waypoint.variable_values = {}

        # Restore variable values
        result = self.waypoint._restore_variable_values()

        # Should return True
        self.assertTrue(result, "Should return True when restoring values")

        # Jet should have no variable values
        self.assertEqual(
            len(self.jet_test.variable_value_ids),
            0,
            "All jet variable values should be removed when waypoint is empty",
        )

    def test_restore_variable_values_basic(self):
        """
        Test _restore_variable_values restores values correctly
        """
        # Set waypoint variable values
        self.waypoint.variable_values = {
            "test_var_1": "restored_value_1",
            "test_var_2": "restored_value_2",
        }

        # Restore variable values
        result = self.waypoint._restore_variable_values()

        # Should return True
        self.assertTrue(result, "Should return True when restoring values")

        # Check values were restored
        self.assertEqual(
            self.jet_test.get_variable_value("test_var_1", no_fallback=True),
            "restored_value_1",
            "Variable 1 should be restored",
        )
        self.assertEqual(
            self.jet_test.get_variable_value("test_var_2", no_fallback=True),
            "restored_value_2",
            "Variable 2 should be restored",
        )

    def test_restore_variable_values_removes_unsaved(self):
        """
        Test _restore_variable_values removes variable values not in waypoint
        """
        # Create variable values in jet
        self.VariableValue.create(
            {
                "variable_id": self.variable_test_1.id,
                "value_char": "value_1",
                "jet_id": self.jet_test.id,
            }
        )
        self.VariableValue.create(
            {
                "variable_id": self.variable_test_2.id,
                "value_char": "value_2",
                "jet_id": self.jet_test.id,
            }
        )
        self.VariableValue.create(
            {
                "variable_id": self.variable_test_3.id,
                "value_char": "value_3",
                "jet_id": self.jet_test.id,
            }
        )

        # Set waypoint to only have variable 1 and 2
        self.waypoint.variable_values = {
            "test_var_1": "value_1",
            "test_var_2": "value_2",
        }

        # Restore variable values
        self.waypoint._restore_variable_values()

        # Variable 3 should be removed
        self.assertIsNone(
            self.jet_test.get_variable_value("test_var_3", no_fallback=True),
            "Variable 3 should be removed",
        )

        # Variables 1 and 2 should still exist
        self.assertEqual(
            self.jet_test.get_variable_value("test_var_1", no_fallback=True),
            "value_1",
            "Variable 1 should still exist",
        )
        self.assertEqual(
            self.jet_test.get_variable_value("test_var_2", no_fallback=True),
            "value_2",
            "Variable 2 should still exist",
        )

    def test_restore_variable_values_updates_existing(self):
        """
        Test _restore_variable_values updates existing variable values
        """
        # Create variable value in jet
        self.VariableValue.create(
            {
                "variable_id": self.variable_test_1.id,
                "value_char": "old_value",
                "jet_id": self.jet_test.id,
            }
        )

        # Set waypoint with new value
        self.waypoint.variable_values = {"test_var_1": "new_value"}

        # Restore variable values
        self.waypoint._restore_variable_values()

        # Value should be updated
        self.assertEqual(
            self.jet_test.get_variable_value("test_var_1", no_fallback=True),
            "new_value",
            "Variable value should be updated",
        )

    def test_save_and_restore_roundtrip(self):
        """
        Test saving and restoring variable values in a roundtrip
        """
        # Create initial variable values
        self.VariableValue.create(
            {
                "variable_id": self.variable_test_1.id,
                "value_char": "initial_value_1",
                "jet_id": self.jet_test.id,
            }
        )
        self.VariableValue.create(
            {
                "variable_id": self.variable_test_2.id,
                "value_char": "initial_value_2",
                "jet_id": self.jet_test.id,
            }
        )

        # Save variable values
        self.waypoint._save_variable_values()

        # Modify jet values
        self.jet_test.set_variable_value("test_var_1", "modified_value_1")
        self.jet_test.set_variable_value("test_var_2", "modified_value_2")
        self.VariableValue.create(
            {
                "variable_id": self.variable_test_3.id,
                "value_char": "new_value",
                "jet_id": self.jet_test.id,
            }
        )

        # Restore variable values
        self.waypoint._restore_variable_values()

        # Values should be restored to original
        self.assertEqual(
            self.jet_test.get_variable_value("test_var_1", no_fallback=True),
            "initial_value_1",
            "Variable 1 should be restored to original value",
        )
        self.assertEqual(
            self.jet_test.get_variable_value("test_var_2", no_fallback=True),
            "initial_value_2",
            "Variable 2 should be restored to original value",
        )
        # Variable 3 should be removed (not in saved waypoint)
        self.assertIsNone(
            self.jet_test.get_variable_value("test_var_3", no_fallback=True),
            "Variable 3 should be removed",
        )

    def test_write_waypoint_template_draft_allowed(self):
        """
        Test that modifying waypoint_template_id is allowed when state is draft
        """
        # Create waypoint in draft state
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint Draft",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "draft",
            }
        )

        # Should be able to change template in draft state
        waypoint.write({"waypoint_template_id": self.waypoint_template_2.id})
        self.assertEqual(
            waypoint.waypoint_template_id.id,
            self.waypoint_template_2.id,
            "Should be able to change template in draft state",
        )

    def test_write_waypoint_template_not_draft_raises_error(self):
        """
        Test that modifying waypoint_template_id raises ValidationError
        when state is not draft
        """
        # Create waypoint in ready state
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint Ready",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "ready",
            }
        )

        # Should raise ValidationError when trying to change template
        with self.assertRaises(ValidationError) as context:
            waypoint.write({"waypoint_template_id": self.waypoint_template_2.id})

        self.assertIn(
            "draft state",
            str(context.exception),
            "Should raise ValidationError about draft state",
        )

    def test_write_waypoint_template_same_value_allowed(self):
        """
        Test that setting waypoint_template_id to the same value is allowed
        even when not in draft state
        """
        # Create waypoint in ready state
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint Ready",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "ready",
            }
        )
        original_template_id = waypoint.waypoint_template_id.id

        # Should be able to set to the same template
        waypoint.write({"waypoint_template_id": original_template_id})
        self.assertEqual(
            waypoint.waypoint_template_id.id,
            original_template_id,
            "Should be able to set same template value",
        )

    def test_write_other_fields_not_draft_allowed(self):
        """
        Test that modifying other fields is allowed when state is not draft
        """
        # Create waypoint in ready state
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint Ready",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "ready",
            }
        )

        # Should be able to modify other fields
        waypoint.write({"name": "Updated Name"})
        self.assertEqual(
            waypoint.name,
            "Updated Name",
            "Should be able to modify other fields when not in draft",
        )

    def test_prepare_without_flight_plan(self):
        """
        Test prepare() when waypoint template has no plan_create_id
        """
        # Create waypoint template without plan_create_id
        waypoint_template_no_plan = self.JetWaypointTemplate.create(
            {
                "name": "Test Waypoint Template No Plan",
                "jet_template_id": self.jet_template_test.id,
            }
        )

        # Create waypoint in draft state
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint No Plan",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": waypoint_template_no_plan.id,
                "state": "draft",
            }
        )

        # Call prepare
        result = waypoint.prepare()

        # Should return True and set state to ready
        self.assertTrue(result, "Should return True")
        self.assertEqual(
            waypoint.state,
            "ready",
            "State should be set to ready when no flight plan",
        )

    def test_prepare_without_flight_plan_with_is_destination(self):
        """
        Test prepare() when waypoint template has no plan_create_id
        and is_destination=True
        Should automatically call fly_to() when prepare completes
        """
        # Create waypoint template without plan_create_id
        waypoint_template_no_plan = self.JetWaypointTemplate.create(
            {
                "name": "Test Waypoint Template No Plan Destination",
                "jet_template_id": self.jet_template_test.id,
            }
        )

        # Create waypoint in draft state with is_destination=True
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint No Plan Destination",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": waypoint_template_no_plan.id,
                "state": "draft",
            }
        )

        # Call prepare
        result = waypoint.prepare(is_destination=True)

        # Should return True
        self.assertTrue(result, "Should return True")
        # State should be set to current (because fly_to() was called)
        # Since there's no previous waypoint and no plan_arrive_id,
        # fly_to() sets state to arriving and calls _arrive() which sets it to current
        self.assertEqual(
            waypoint.state,
            "current",
            "State should be set to current after fly_to() and _arrive()",
        )
        # Waypoint should be set as current waypoint
        self.assertEqual(
            self.jet_test.waypoint_id.id,
            waypoint.id,
            "Waypoint should be set as current waypoint after fly_to()",
        )
        # is_destination should be cleared after arriving
        self.assertFalse(
            waypoint.is_destination,
            "is_destination should be cleared after arriving",
        )

    def test_prepare_with_flight_plan_success(self):
        """
        Test prepare() when waypoint template has plan_create_id and plan succeeds
        """
        # Set template to use success plan
        self.waypoint_template.plan_create_id = self.plan_success.id

        # Create waypoint in draft state
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint With Plan",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "draft",
            }
        )

        # Call prepare - plan executes synchronously in tests
        result = waypoint.prepare()

        # Should return True
        self.assertTrue(result, "Should return True")

        # State should be set to ready after successful plan completion
        # (plan executes synchronously in tests, preparing -> ready)
        self.assertEqual(
            waypoint.state,
            "ready",
            "State should be set to ready after successful plan completion",
        )
        # Waypoint should NOT be set as current waypoint after preparing
        # (only arriving sets waypoint as current)
        self.assertNotEqual(
            self.jet_test.waypoint_id.id if self.jet_test.waypoint_id else False,
            waypoint.id,
            "Waypoint should not be set as current waypoint after preparing",
        )

    def test_waypoint_variable_in_python_command_prepare(self):
        """
        Test that 'waypoint' variable is available in Python commands
        run for a waypoint plan (plan_create) and its id is used as exit code
        """
        # Set template to use waypoint check plan
        self.waypoint_template.plan_create_id = self.plan_waypoint_check.id

        # Create waypoint in draft state
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint For Variable Check",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "draft",
            }
        )

        # Call prepare - plan executes synchronously in tests
        waypoint.prepare()

        # Find the plan log created by prepare
        plan_log = self.PlanLog.search(
            [("waypoint_id", "=", waypoint.id)],
            order="create_date desc",
            limit=1,
        )
        self.assertTrue(plan_log, "Plan log should be created")

        # Plan exit code (plan_status) must equal waypoint id
        self.assertEqual(
            plan_log.plan_status,
            waypoint.id,
            "Plan status must equal waypoint id (from waypoint variable)",
        )

    def test_waypoint_variable_in_python_command_arrive(self):
        """
        Test that 'waypoint' variable is available in Python commands
        run for a waypoint arrive plan and its id is used as exit code
        """
        # Create waypoint template with plan_arrive_id
        waypoint_template = self.JetWaypointTemplate.create(
            {
                "name": "Waypoint Template For Arrive Check",
                "jet_template_id": self.jet_template_test.id,
                "plan_arrive_id": self.plan_waypoint_check.id,
            }
        )

        # Create waypoint in arriving state (no previous waypoint)
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint For Arrive Variable Check",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": waypoint_template.id,
                "state": "arriving",
            }
        )

        # Call arrive - plan executes synchronously in tests
        waypoint._arrive()

        # Find the plan log created by arrive
        plan_log = self.PlanLog.search(
            [("waypoint_id", "=", waypoint.id)],
            order="create_date desc",
            limit=1,
        )
        self.assertTrue(plan_log, "Plan log should be created")

        # Plan exit code (plan_status) must equal waypoint id
        self.assertEqual(
            plan_log.plan_status,
            waypoint.id,
            "Plan status must equal waypoint id (from waypoint variable)",
        )

    def test_prepare_with_flight_plan_error(self):
        """
        Test prepare() when waypoint template has plan_create_id and plan fails
        """
        # Set template to use error plan
        self.waypoint_template.plan_create_id = self.plan_error.id

        # Create waypoint in draft state
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint With Plan Error",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "draft",
            }
        )

        # Call prepare - plan executes synchronously in tests
        with mute_logger(
            "odoo.addons.cetmix_tower_server.models.cx_tower_jet_waypoint"
        ):
            result = waypoint.prepare()

        # Should return True
        self.assertTrue(result, "Should return True")

        # State should be set to error after failed plan completion
        # (plan executes synchronously in tests)
        self.assertEqual(
            waypoint.state,
            "error",
            "State should be set to error after failed plan completion",
        )
        # Waypoint should not be set as current waypoint on error
        self.assertNotEqual(
            self.jet_test.waypoint_id.id,
            waypoint.id,
            "Waypoint should not be set as current waypoint after failed prepare",
        )

    def test_prepare_not_draft_state(self):
        """
        Test prepare() when waypoint is not in draft state
        """
        # Create waypoint in ready state
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint Ready",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "ready",
            }
        )

        # Call prepare. This will log and error because waypoint is not in draft state
        with mute_logger(
            "odoo.addons.cetmix_tower_server.models.cx_tower_jet_waypoint"
        ):
            with self.assertRaises(ValidationError):
                waypoint.prepare()

    def test_plan_finished_preparing_success(self):
        """
        Test _plan_finished when waypoint is in preparing state and plan succeeds
        """
        # Create waypoint in preparing state (simulating async plan execution)
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint Preparing",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "preparing",
            }
        )

        # Create plan log with success status
        plan_log = self.PlanLog.create(
            {
                "server_id": self.jet_test.server_id.id,
                "plan_id": self.plan_success.id,
                "plan_status": 0,  # Success
            }
        )

        # Call _plan_finished
        result = waypoint._plan_finished(plan_log)

        # Should return True
        self.assertTrue(result, "Should return True")
        # State should be set to ready
        # (preparing -> ready, not current)
        self.assertEqual(
            waypoint.state,
            "ready",
            "State should be set to ready after successful plan completion",
        )
        # Waypoint should NOT be set as current waypoint after preparing
        # (only arriving sets waypoint as current)
        self.assertNotEqual(
            self.jet_test.waypoint_id.id if self.jet_test.waypoint_id else False,
            waypoint.id,
            "Waypoint should not be set as current waypoint after preparing",
        )

    def test_plan_finished_preparing_success_with_is_destination(self):
        """
        Test _plan_finished when waypoint is in preparing state with is_destination=True
        Should automatically call fly_to() when preparing finishes
        """
        # Create waypoint in preparing state with is_destination=True
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint Preparing Destination",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "preparing",
                "is_destination": True,
            }
        )

        # Create plan log with success status
        plan_log = self.PlanLog.create(
            {
                "server_id": self.jet_test.server_id.id,
                "plan_id": self.plan_success.id,
                "plan_status": 0,  # Success
            }
        )

        # Call _plan_finished
        result = waypoint._plan_finished(plan_log)

        # Should return True
        self.assertTrue(result, "Should return True")
        # State should be set to arriving (because fly_to() was called)
        # Since there's no previous waypoint and no plan_arrive_id,
        # fly_to() sets state to arriving and calls _arrive() which sets it to current
        self.assertEqual(
            waypoint.state,
            "current",
            "State should be set to current after fly_to() and _arrive()",
        )
        # Waypoint should be set as current waypoint
        self.assertEqual(
            self.jet_test.waypoint_id.id,
            waypoint.id,
            "Waypoint should be set as current waypoint after fly_to()",
        )
        # is_destination should be cleared after arriving
        self.assertFalse(
            waypoint.is_destination,
            "is_destination should be cleared after arriving",
        )

    def test_plan_finished_arriving_success(self):
        """
        Test _plan_finished when waypoint is in arriving state and plan succeeds
        """
        # Create waypoint in arriving state (simulating async plan execution)
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint Arriving",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "arriving",
            }
        )

        # Create plan log with success status
        plan_log = self.PlanLog.create(
            {
                "server_id": self.jet_test.server_id.id,
                "plan_id": self.plan_success.id,
                "plan_status": 0,  # Success
            }
        )

        # Call _plan_finished
        result = waypoint._plan_finished(plan_log)

        # Should return True
        self.assertTrue(result, "Should return True")
        # State should be set to current
        # (waypoint becomes current after successful arrive)
        self.assertEqual(
            waypoint.state,
            "current",
            "State should be set to current after successful plan completion",
        )
        # Waypoint should be set as current waypoint
        self.assertEqual(
            self.jet_test.waypoint_id.id,
            waypoint.id,
            "Waypoint should be set as current waypoint after successful arrive",
        )

    def test_plan_finished_leaving_success(self):
        """
        Test _plan_finished when waypoint is in leaving state and plan succeeds
        """
        # Create current waypoint in current state
        current_waypoint = self.JetWaypoint.create(
            {
                "name": "Current Waypoint",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "current",
            }
        )
        self.jet_test.waypoint_id = current_waypoint.id

        # Create destination waypoint in arriving state
        destination_waypoint = self.JetWaypoint.create(
            {
                "name": "Destination Waypoint",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "is_destination": True,
                "state": "arriving",
            }
        )

        # Set current waypoint to leaving state
        # readonly=True only affects UI, can be written programmatically
        current_waypoint.write({"state": "leaving"})

        # Create plan log with success status
        plan_log = self.PlanLog.create(
            {
                "server_id": self.jet_test.server_id.id,
                "plan_id": self.plan_success.id,
                "plan_status": 0,  # Success
            }
        )

        # Call _plan_finished on leaving waypoint
        result = current_waypoint._plan_finished(plan_log)

        # Should return True
        self.assertTrue(result, "Should return True")
        # Leaving waypoint state should be set to ready
        self.assertEqual(
            current_waypoint.state,
            "ready",
            "Leaving waypoint state should be set to ready",
        )
        # Destination waypoint should have _arrive() called
        # (state should be current if no plan_arrive_id)
        # Since waypoint_template has no plan_arrive_id by default,
        # _arrive() sets state to current
        self.assertEqual(
            destination_waypoint.state,
            "current",
            "Destination waypoint should have _arrive() called",
        )
        # Destination waypoint should be set as current waypoint
        self.assertEqual(
            self.jet_test.waypoint_id.id,
            destination_waypoint.id,
            "Destination waypoint should be set as current waypoint"
            " after leaving completes",
        )

    def test_plan_finished_deleting_success(self):
        """
        Test _plan_finished when waypoint is in deleting state and plan succeeds
        """
        # Create waypoint template with plan_delete_id
        waypoint_template = self.JetWaypointTemplate.create(
            {
                "name": "Test Template With Delete Plan",
                "jet_template_id": self.jet_template_test.id,
                "plan_delete_id": self.plan_success.id,
            }
        )

        # Create waypoint and set it as current
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint Deleting",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": waypoint_template.id,
                "state": "ready",
            }
        )
        self.jet_test.waypoint_id = waypoint.id

        # Set waypoint to deleting state
        # readonly=True only affects UI, can be written programmatically
        waypoint.write({"state": "deleting"})

        # Create plan log with success status
        plan_log = self.PlanLog.create(
            {
                "server_id": self.jet_test.server_id.id,
                "plan_id": self.plan_success.id,
                "plan_status": 0,  # Success
            }
        )

        # Call _plan_finished
        result = waypoint._plan_finished(plan_log)

        # Should return True
        self.assertTrue(result, "Should return True")
        # Waypoint should be unlinked (deleted)
        # State is set to "deleted" before unlink
        self.assertFalse(
            waypoint.exists(),
            "Waypoint should be unlinked after successful delete plan",
        )
        # Jet waypoint_id should be set to False
        self.assertFalse(
            self.jet_test.waypoint_id,
            "Jet waypoint_id should be set to False after successful delete",
        )

    def test_plan_finished_error(self):
        """
        Test _plan_finished when plan fails (plan_status != 0)
        """
        # Create waypoint in preparing state (simulating async plan execution)
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint Preparing",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "preparing",
            }
        )
        original_waypoint_id = (
            self.jet_test.waypoint_id.id if self.jet_test.waypoint_id else False
        )

        # Create plan log with error status
        plan_log = self.PlanLog.create(
            {
                "server_id": self.jet_test.server_id.id,
                "plan_id": self.plan_error.id,
                "plan_status": 1,  # Error
            }
        )

        # Call _plan_finished
        with mute_logger(
            "odoo.addons.cetmix_tower_server.models.cx_tower_jet_waypoint"
        ):
            result = waypoint._plan_finished(plan_log)

        # Should return True
        self.assertTrue(result, "Should return True")
        # State should be set to error
        self.assertEqual(
            waypoint.state,
            "error",
            "State should be set to error after failed plan completion",
        )
        # Waypoint should not be set as current waypoint
        if original_waypoint_id:
            self.assertEqual(
                self.jet_test.waypoint_id.id,
                original_waypoint_id,
                "Current waypoint should not change on error",
            )
        else:
            self.assertFalse(
                self.jet_test.waypoint_id,
                "Current waypoint should remain False on error",
            )

    def test_plan_finished_error_arriving(self):
        """
        Test _plan_finished when waypoint is in arriving state and plan fails
        """
        # Create waypoint in arriving state
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint Arriving",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "arriving",
            }
        )

        # Create plan log with error status
        plan_log = self.PlanLog.create(
            {
                "server_id": self.jet_test.server_id.id,
                "plan_id": self.plan_error.id,
                "plan_status": 1,  # Error
            }
        )

        # Call _plan_finished
        with mute_logger(
            "odoo.addons.cetmix_tower_server.models.cx_tower_jet_waypoint"
        ):
            result = waypoint._plan_finished(plan_log)

        # Should return True
        self.assertTrue(result, "Should return True")
        # State should be set to error
        self.assertEqual(
            waypoint.state,
            "error",
            "State should be set to error after failed plan completion",
        )
        # Waypoint should not be set as current waypoint on error
        self.assertNotEqual(
            self.jet_test.waypoint_id.id if self.jet_test.waypoint_id else False,
            waypoint.id,
            "Waypoint should not be set as current waypoint after failed arrive",
        )

    def test_get_custom_variable_values_with_metadata(self):
        """
        Test _get_custom_variable_values with metadata
        """
        # Set template to use success plan
        self.waypoint_template.plan_create_id = self.plan_success.id

        # Create waypoint with metadata
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint With Metadata",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "draft",
                "metadata": {"key1": "value1", "key2": "value2", "env": "production"},
            }
        )

        # Call prepare to trigger flight plan
        waypoint.prepare()

        # Find the plan log created by prepare
        plan_log = self.PlanLog.search(
            [
                ("waypoint_id", "=", waypoint.id),
            ],
            order="create_date desc",
            limit=1,
        )
        self.assertTrue(plan_log, "Plan log should be created")

        # Check custom variable values in plan log
        self.assertEqual(
            plan_log.variable_values.get("__waypoint"),
            waypoint.reference,
            "__waypoint should match waypoint reference",
        )
        self.assertEqual(
            plan_log.variable_values.get("__waypoint_type"),
            self.waypoint_template.reference,
            "__waypoint_type should match waypoint template reference",
        )
        self.assertEqual(
            plan_log.variable_values.get("__waypoint_state"),
            "preparing",
            "__waypoint_state should be preparing",
        )
        # Check metadata keys
        self.assertEqual(
            plan_log.variable_values.get("__waypoint_key1"),
            "value1",
            "__waypoint_key1 should match metadata value",
        )
        self.assertEqual(
            plan_log.variable_values.get("__waypoint_key2"),
            "value2",
            "__waypoint_key2 should match metadata value",
        )
        self.assertEqual(
            plan_log.variable_values.get("__waypoint_env"),
            "production",
            "__waypoint_env should match metadata value",
        )

    def test_get_custom_variable_values_without_metadata(self):
        """
        Test _get_custom_variable_values without metadata
        """
        # Set template to use success plan
        self.waypoint_template.plan_create_id = self.plan_success.id

        # Create waypoint without metadata
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint Without Metadata",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "draft",
            }
        )

        # Call prepare to trigger flight plan
        waypoint.prepare()

        # Find the plan log created by prepare
        plan_log = self.PlanLog.search(
            [("waypoint_id", "=", waypoint.id)],
            order="create_date desc",
            limit=1,
        )
        self.assertTrue(plan_log, "Plan log should be created")

        # Check basic custom variable values
        self.assertEqual(
            plan_log.variable_values.get("__waypoint"),
            waypoint.reference,
            "__waypoint should match waypoint reference",
        )
        self.assertEqual(
            plan_log.variable_values.get("__waypoint_type"),
            self.waypoint_template.reference,
            "__waypoint_type should match waypoint template reference",
        )
        self.assertEqual(
            plan_log.variable_values.get("__waypoint_state"),
            "preparing",
            "__waypoint_state should be preparing",
        )
        # Check that metadata keys are not present
        self.assertNotIn(
            "__waypoint_key1",
            plan_log.variable_values,
            "Metadata keys should not be present when metadata is empty",
        )

    def test_leave_from_current_state(self):
        """
        Test _leave() when waypoint is in current state
        """
        # Create waypoint in current state
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint Current",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "current",
            }
        )
        self.jet_test.waypoint_id = waypoint.id

        # Call _leave
        result = waypoint._leave()

        # Should return True
        self.assertTrue(result, "Should return True")
        # State should be set to ready
        # (_leave() completes immediately when no plan_leave_id in tests)
        self.assertEqual(
            waypoint.state,
            "ready",
            "State should be set to ready after leaving completes",
        )

    def test_fly_to_from_current_waypoint(self):
        """
        Test fly_to() when previous waypoint is in current state
        """
        # Create current waypoint
        current_waypoint = self.JetWaypoint.create(
            {
                "name": "Current Waypoint",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "current",
            }
        )
        self.jet_test.waypoint_id = current_waypoint.id

        # Create destination waypoint
        destination_waypoint = self.JetWaypoint.create(
            {
                "name": "Destination Waypoint",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "ready",
            }
        )

        # Call fly_to on destination waypoint
        result = destination_waypoint.fly_to()

        # Should return True
        self.assertTrue(result, "Should return True")
        # Current waypoint should be in ready state
        # (_leave() completes immediately when no plan_leave_id in tests)
        self.assertEqual(
            current_waypoint.state,
            "ready",
            "Current waypoint should be in ready state after leaving completes",
        )
        # Destination waypoint should be in current state
        # (_arrive() completes immediately when no plan_arrive_id in tests)
        self.assertEqual(
            destination_waypoint.state,
            "current",
            "Destination waypoint should be in current state after arriving",
        )
        # Destination waypoint should be set as current waypoint
        self.assertEqual(
            self.jet_test.waypoint_id.id,
            destination_waypoint.id,
            "Destination waypoint should be set as current waypoint",
        )

    def test_fly_to_leave_failure_does_not_keep_destination_arriving(self):
        """
        Regression: if source leave plan fails during fly_to(),
        destination must not stay in arriving.
        """
        # Create template with failing leave plan.
        waypoint_template_with_leave_error = self.JetWaypointTemplate.create(
            {
                "name": "Template Leave Error",
                "jet_template_id": self.jet_template_test.id,
                "plan_leave_id": self.plan_error.id,
            }
        )

        # Create current waypoint that will fail while leaving.
        current_waypoint = self.JetWaypoint.create(
            {
                "name": "Current Waypoint Failing Leave",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": waypoint_template_with_leave_error.id,
                "state": "current",
            }
        )
        self.jet_test.waypoint_id = current_waypoint.id

        # Create destination waypoint (target of fly_to).
        destination_waypoint = self.JetWaypoint.create(
            {
                "name": "Destination Waypoint Stuck Arriving",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "ready",
            }
        )

        # Execute fly_to; leaving fails synchronously in tests.
        with mute_logger(
            "odoo.addons.cetmix_tower_server.models.cx_tower_jet_waypoint"
        ):
            result = destination_waypoint.fly_to()

        self.assertFalse(result, "fly_to() should return False when leave fails")
        self.assertEqual(
            current_waypoint.state,
            "error",
            "Source waypoint should become error after failed leave plan",
        )
        self.assertNotEqual(
            destination_waypoint.state,
            "arriving",
            "Destination waypoint must be reverted from arriving when leave fails",
        )
        self.assertFalse(
            destination_waypoint.is_destination,
            "Destination flag must be cleared when leave fails",
        )

    def test_unlink_current_state_raises_error(self):
        """
        Test unlink() when waypoint is in current state raises ValidationError
        """
        # Create waypoint in current state
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint Current",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "current",
            }
        )
        self.jet_test.waypoint_id = waypoint.id

        # Should raise ValidationError when trying to delete

        with self.assertRaises(ValidationError) as context:
            waypoint.unlink()

        self.assertIn(
            "current waypoint",
            str(context.exception),
            "Should raise ValidationError about current waypoint",
        )

    def test_unlink_current_state_with_no_raise_context(self):
        """
        Test unlink() when waypoint is in current state
        with 'waypoint_no_raise_on_delete' context.
        The context prevents exception but waypoint is not deleted.
        """
        # Create waypoint in current state
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint Current",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "current",
            }
        )
        self.jet_test.waypoint_id = waypoint.id
        waypoint_id = waypoint.id

        # Mute logger error for this test
        with mute_logger(
            "odoo.addons.cetmix_tower_server.models.cx_tower_jet_waypoint"
        ):
            # Should not raise error with waypoint_no_raise_on_delete context
            waypoint.with_context(waypoint_no_raise_on_delete=True).unlink()

        # Waypoint should still exist (not deleted)
        # The context only prevents exception, but doesn't allow deletion
        self.assertTrue(
            waypoint.exists(),
            "Waypoint should still exist - context only prevents exception",
        )
        self.assertEqual(
            waypoint.id,
            waypoint_id,
            "Waypoint ID should remain the same",
        )
        self.assertEqual(
            waypoint.state,
            "current",
            "Waypoint state should remain current",
        )

    def test_prepare_saves_variable_values(self):
        """
        Test that prepare() saves variable values when state changes to ready
        """
        # Set some variable values on the jet
        self.jet_test.set_variable_value("test_var_1", "value1")
        self.jet_test.set_variable_value("test_var_2", "value2")

        # Create waypoint in draft state
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "draft",
            }
        )

        # Ensure waypoint has no plan_create_id (so it goes directly to ready)
        waypoint.waypoint_template_id.plan_create_id = False

        # Call prepare
        waypoint.prepare()

        # Variable values should be saved in waypoint
        variable_values = waypoint.variable_values or {}
        self.assertEqual(
            variable_values.get("test_var_1"),
            "value1",
            "Variable value should be saved when preparing",
        )
        self.assertEqual(
            variable_values.get("test_var_2"),
            "value2",
            "Variable value should be saved when preparing",
        )

    def test_prepare_with_plan_saves_variable_values(self):
        """
        Test that prepare() saves variable values when plan completes
        """
        # Set some variable values on the jet
        self.jet_test.set_variable_value("test_var_1", "value1")
        self.jet_test.set_variable_value("test_var_2", "value2")

        # Create waypoint template with plan_create_id
        waypoint_template = self.JetWaypointTemplate.create(
            {
                "name": "Test Template",
                "jet_template_id": self.jet_template_test.id,
                "plan_create_id": self.plan_success.id,
            }
        )

        # Create waypoint in draft state
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": waypoint_template.id,
                "state": "draft",
            }
        )

        # Call prepare (plan executes synchronously in tests)
        waypoint.prepare()

        # Variable values should be saved in waypoint after plan completes
        variable_values = waypoint.variable_values or {}
        self.assertEqual(
            variable_values.get("test_var_1"),
            "value1",
            "Variable value should be saved when preparing completes",
        )
        self.assertEqual(
            variable_values.get("test_var_2"),
            "value2",
            "Variable value should be saved when preparing completes",
        )

    def test_leave_saves_variable_values(self):
        """
        Test that _leave() saves variable values when state changes to ready
        """
        # Set some variable values on the jet
        self.jet_test.set_variable_value("test_var_1", "value1")
        self.jet_test.set_variable_value("test_var_2", "value2")

        # Create waypoint in current state
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "current",
            }
        )
        self.jet_test.waypoint_id = waypoint.id

        # Ensure waypoint has no plan_leave_id (so it goes directly to ready)
        waypoint.waypoint_template_id.plan_leave_id = False

        # Call _leave
        waypoint._leave()

        # Variable values should be saved in waypoint
        variable_values = waypoint.variable_values or {}
        self.assertEqual(
            variable_values.get("test_var_1"),
            "value1",
            "Variable value should be saved when leaving",
        )
        self.assertEqual(
            variable_values.get("test_var_2"),
            "value2",
            "Variable value should be saved when leaving",
        )

    def test_leave_with_plan_saves_variable_values(self):
        """
        Test that _leave() saves variable values when plan completes
        """
        # Set some variable values on the jet
        self.jet_test.set_variable_value("test_var_1", "value1")
        self.jet_test.set_variable_value("test_var_2", "value2")

        # Create waypoint template with plan_leave_id
        waypoint_template = self.JetWaypointTemplate.create(
            {
                "name": "Test Template",
                "jet_template_id": self.jet_template_test.id,
                "plan_leave_id": self.plan_success.id,
            }
        )

        # Create waypoint in current state
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": waypoint_template.id,
                "state": "current",
            }
        )
        self.jet_test.waypoint_id = waypoint.id

        # Call _leave (plan executes synchronously in tests)
        waypoint._leave()

        # Variable values should be saved in waypoint after plan completes
        variable_values = waypoint.variable_values or {}
        self.assertEqual(
            variable_values.get("test_var_1"),
            "value1",
            "Variable value should be saved when leaving completes",
        )
        self.assertEqual(
            variable_values.get("test_var_2"),
            "value2",
            "Variable value should be saved when leaving completes",
        )

    def test_fly_to_restores_variable_values(self):
        """
        Test that fly_to() restores variable values when state changes to arriving
        """
        # Create waypoint with saved variable values
        waypoint = self.JetWaypoint.create(
            {
                "name": "Test Waypoint",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "ready",
                "variable_values": {
                    "test_var_1": "saved_value1",
                    "test_var_2": "saved_value2",
                },
            }
        )

        # Set different values on the jet
        self.jet_test.set_variable_value("test_var_1", "current_value1")
        self.jet_test.set_variable_value("test_var_2", "current_value2")

        # Call fly_to (no previous waypoint)
        waypoint.fly_to()

        # Variable values should be restored from waypoint
        self.assertEqual(
            self.jet_test.get_variable_value("test_var_1"),
            "saved_value1",
            "Variable value should be restored when flying to waypoint",
        )
        self.assertEqual(
            self.jet_test.get_variable_value("test_var_2"),
            "saved_value2",
            "Variable value should be restored when flying to waypoint",
        )

    def test_fly_to_restores_variable_values_with_previous_waypoint(self):
        """
        Test that fly_to() restores variable values
        after previous waypoint saves its values
        """
        # Create previous waypoint in current state
        previous_waypoint = self.JetWaypoint.create(
            {
                "name": "Previous Waypoint",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "current",
            }
        )
        self.jet_test.waypoint_id = previous_waypoint.id

        # Set variable values on the jet
        self.jet_test.set_variable_value("test_var_1", "previous_value1")
        self.jet_test.set_variable_value("test_var_2", "previous_value2")

        # Create destination waypoint with saved variable values
        destination_waypoint = self.JetWaypoint.create(
            {
                "name": "Destination Waypoint",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "ready",
                "variable_values": {
                    "test_var_1": "destination_value1",
                    "test_var_2": "destination_value2",
                },
            }
        )

        # Ensure previous waypoint has no plan_leave_id (so it saves values immediately)
        previous_waypoint.waypoint_template_id.plan_leave_id = False

        # Call fly_to
        destination_waypoint.fly_to()

        # Previous waypoint should have saved its values
        previous_values = previous_waypoint.variable_values or {}
        self.assertEqual(
            previous_values.get("test_var_1"),
            "previous_value1",
            "Previous waypoint should save its variable values",
        )

        # Variable values should be restored from destination waypoint
        self.assertEqual(
            self.jet_test.get_variable_value("test_var_1"),
            "destination_value1",
            "Variable value should be restored from destination waypoint",
        )
        self.assertEqual(
            self.jet_test.get_variable_value("test_var_2"),
            "destination_value2",
            "Variable value should be restored from destination waypoint",
        )

    def test_arriving_error_restores_variable_values(self):
        """
        Test that when arriving fails,
        variable values are restored from current waypoint
        """
        # Create current waypoint with saved variable values
        current_waypoint = self.JetWaypoint.create(
            {
                "name": "Current Waypoint",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "current",
                "variable_values": {
                    "test_var_1": "current_value1",
                    "test_var_2": "current_value2",
                },
            }
        )
        self.jet_test.waypoint_id = current_waypoint.id

        # Create arriving waypoint
        arriving_waypoint = self.JetWaypoint.create(
            {
                "name": "Arriving Waypoint",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "state": "arriving",
            }
        )

        # Set different values on the jet
        self.jet_test.set_variable_value("test_var_1", "arriving_value1")
        self.jet_test.set_variable_value("test_var_2", "arriving_value2")

        # Create plan log with error status
        plan_log = self.PlanLog.create(
            {
                "server_id": self.jet_test.server_id.id,
                "plan_id": self.plan_error.id,
                "plan_status": -100,  # Error
            }
        )

        # Call _plan_finished with error
        with mute_logger(
            "odoo.addons.cetmix_tower_server.models.cx_tower_jet_waypoint"
        ):
            arriving_waypoint._plan_finished(plan_log)

        # Variable values should be restored from current waypoint
        self.assertEqual(
            self.jet_test.get_variable_value("test_var_1"),
            "current_value1",
            "Variable value should be restored from current waypoint on error",
        )
        self.assertEqual(
            self.jet_test.get_variable_value("test_var_2"),
            "current_value2",
            "Variable value should be restored from current waypoint on error",
        )

        # Current waypoint state should be "current"
        self.assertEqual(
            current_waypoint.state,
            "current",
            "Current waypoint state should remain current",
        )

        # Arriving waypoint state should be "error"
        self.assertEqual(
            arriving_waypoint.state,
            "error",
            "Arriving waypoint state should be error",
        )

    # ------------------------------------
    # --- _check_is_destination tests ----
    # ------------------------------------

    def _make_destination_waypoint(self, name, jet=None):
        """
        Helper: create a waypoint and atomically transition it to the
        ``preparing`` state with ``is_destination=True``.

        This mirrors what ``prepare(is_destination=True)`` does internally
        when the waypoint template has a ``plan_create_id`` (it writes
        ``state=preparing`` + ``is_destination`` in one call and does not
        proceed to ``fly_to()``). Using that path keeps ``is_destination``
        stable for subsequent constraint assertions, whereas calling
        ``prepare()`` without a plan triggers ``fly_to()`` → ``_arrive()``,
        which clears ``is_destination`` immediately.

        Args:
            name (str): Name of the waypoint.
            jet (cx.tower.jet, optional): Target jet. Defaults to jet_test.

        Returns:
            cx.tower.jet.waypoint: Waypoint in ``preparing`` state with
                ``is_destination=True``.
        """
        if jet is None:
            jet = self.jet_test
        waypoint = self.JetWaypoint.create(
            {
                "name": name,
                "jet_id": jet.id,
                "waypoint_template_id": self.waypoint_template.id,
            }
        )
        waypoint.write({"state": "preparing", "is_destination": True})
        return waypoint

    def test_check_is_destination_single_allowed(self):
        """
        Preparing one destination waypoint for a jet via prepare() is valid.
        """
        waypoint = self._make_destination_waypoint("Destination Waypoint")
        self.assertTrue(waypoint.is_destination)

    def test_check_is_destination_different_jets_allowed(self):
        """
        Each jet may independently have its own destination waypoint.
        """
        self._make_destination_waypoint("Destination Jet Test", jet=self.jet_test)
        waypoint_other = self._make_destination_waypoint(
            "Destination Jet Odoo", jet=self.jet_odoo
        )
        self.assertTrue(waypoint_other.is_destination)

    def test_check_is_destination_false_ignored(self):
        """
        Waypoints with is_destination=False are never checked, even when
        another destination already exists for the same jet.
        """
        self._make_destination_waypoint("Existing Destination")
        # Creating a non-destination waypoint must not raise.
        non_dest = self.JetWaypoint.create(
            {
                "name": "Non Destination",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
                "is_destination": False,
            }
        )
        self.assertFalse(non_dest.is_destination)

    def _assert_state_blocks_destination(self, state):
        """
        Helper: create a waypoint, force it into ``state``, then assert that
        writing ``is_destination=True`` raises a ValidationError.

        Args:
            state (str): Waypoint state to test.
        """
        waypoint = self.JetWaypoint.create(
            {
                "name": f"Waypoint in {state}",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
            }
        )
        waypoint.write({"state": state})
        with self.assertRaises(ValidationError):
            waypoint.write({"is_destination": True})

    def test_check_is_destination_draft_state_raises(self):
        """
        Setting is_destination=True directly on a waypoint in the 'draft' state
        must raise a ValidationError.
        Use prepare(is_destination=True) to designate a destination waypoint.
        """
        self._assert_state_blocks_destination("draft")

    def test_check_is_destination_error_state_raises(self):
        """
        Setting is_destination=True on a waypoint in the 'error' state
        must raise a ValidationError.
        """
        self._assert_state_blocks_destination("error")

    def test_check_is_destination_leaving_state_raises(self):
        """
        Setting is_destination=True on a waypoint in the 'leaving' state
        must raise a ValidationError.
        """
        self._assert_state_blocks_destination("leaving")

    def test_check_is_destination_deleting_state_raises(self):
        """
        Setting is_destination=True on a waypoint in the 'deleting' state
        must raise a ValidationError.
        """
        self._assert_state_blocks_destination("deleting")

    def test_check_is_destination_deleted_state_raises(self):
        """
        Setting is_destination=True on a waypoint in the 'deleted' state
        must raise a ValidationError.
        """
        self._assert_state_blocks_destination("deleted")

    def test_check_is_destination_duplicate_on_create_raises(self):
        """
        Setting is_destination via prepare() then trying to prepare a second
        destination for the same jet must raise a ValidationError.
        """
        self._make_destination_waypoint("First Destination")
        second = self.JetWaypoint.create(
            {
                "name": "Second Destination",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
            }
        )
        with self.assertRaises(ValidationError):
            second.write({"state": "ready", "is_destination": True})

    def test_check_is_destination_duplicate_on_write_raises(self):
        """
        Writing is_destination=True on a second ready waypoint for the same jet
        must raise a ValidationError.
        """
        self._make_destination_waypoint("Existing Destination")
        second = self.JetWaypoint.create(
            {
                "name": "Second Waypoint",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
            }
        )
        second.write({"state": "ready"})
        with self.assertRaises(ValidationError):
            second.write({"is_destination": True})

    def test_check_is_destination_duplicate_within_same_batch_raises(self):
        """
        Writing is_destination=True on two ready waypoints for the same jet
        in a single write() call must raise a ValidationError.

        Both records are excluded from the DB search (neither is a destination
        yet), so the constraint must also detect duplicates within the batch.
        """
        wp1 = self.JetWaypoint.create(
            {
                "name": "Batch Destination 1",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
            }
        )
        wp2 = self.JetWaypoint.create(
            {
                "name": "Batch Destination 2",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
            }
        )
        (wp1 | wp2).write({"state": "ready"})
        with self.assertRaises(ValidationError):
            (wp1 | wp2).write({"is_destination": True})

    # ------------------------------------
    # --- unlink destination guard tests -
    # ------------------------------------

    @mute_logger("odoo.addons.cetmix_tower_server.models.cx_tower_jet_waypoint")
    def test_unlink_destination_waypoint_raises(self):
        """
        Deleting a waypoint with is_destination=True must raise a
        ValidationError regardless of state, to prevent the jet from being
        stranded mid-flight while a leave plan is still running.
        """
        waypoint = self._make_destination_waypoint("Active Destination")
        with self.assertRaises(ValidationError):
            waypoint.unlink()

    @mute_logger("odoo.addons.cetmix_tower_server.models.cx_tower_jet_waypoint")
    def test_unlink_destination_waypoint_no_raise_context_logs(self):
        """
        When waypoint_no_raise_on_delete=True is set in context, deleting a
        destination waypoint must not raise but must log the error and skip
        the record.
        """
        waypoint = self._make_destination_waypoint("Active Destination No Raise")
        waypoint.with_context(waypoint_no_raise_on_delete=True).unlink()
        # Record must still exist — it was skipped, not deleted.
        self.assertTrue(waypoint.exists())

    def test_unlink_non_destination_ready_waypoint_allowed(self):
        """
        Deleting a ready waypoint that is NOT a destination must still work.
        """
        waypoint = self.JetWaypoint.create(
            {
                "name": "Ready Non-Destination",
                "jet_id": self.jet_test.id,
                "waypoint_template_id": self.waypoint_template.id,
            }
        )
        waypoint.write({"state": "ready"})
        waypoint.unlink()
        self.assertFalse(waypoint.exists())
