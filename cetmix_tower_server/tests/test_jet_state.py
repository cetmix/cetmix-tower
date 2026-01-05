# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError, ValidationError

from .common_jets import TestTowerJetsCommon


class TestTowerJetState(TestTowerJetsCommon):
    """
    Test the Jet State model functionality
    """

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   set_state Tests
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def test_set_state_success_user_level(self):
        """
        Test set_state succeeds when user has sufficient access level.
        User (level 1) can set state with level 1.
        """
        # Use existing state and set it to User access level (1)
        self.state_running.access_level = "1"
        self.state_running.invalidate_recordset(["access_level"])

        # Ensure user has access to the jet and server
        self.jet_test.write({"user_ids": [(4, self.user.id)]})
        self.server_test_1.write({"user_ids": [(4, self.user.id)]})

        # Set jet to initial state
        self.jet_test.state_id = self.state_initial

        # User should be able to set state
        self.state_running.with_user(self.user).with_context(
            cetmix_tower_no_commit=True
        ).set_state(self.jet_test)
        self.assertEqual(
            self.jet_test.state_id,
            self.state_running,
            "Jet should be set to user-level state by user",
        )

    def test_set_state_success_manager_level(self):
        """
        Test set_state succeeds when manager has sufficient access level.
        Manager (level 2) can set state with level 2.
        """
        # Use existing state and set it to Manager access level (2)
        self.state_stopped.access_level = "2"
        self.state_stopped.invalidate_recordset(["access_level"])

        # Ensure manager has access to the jet and server
        self.jet_test.write({"manager_ids": [(4, self.manager.id)]})
        self.server_test_1.write({"manager_ids": [(4, self.manager.id)]})

        # Set jet to running state (which has action to stopped)
        self.jet_test.state_id = self.state_running

        # Manager should be able to set state
        self.state_stopped.with_user(self.manager).with_context(
            cetmix_tower_no_commit=True
        ).set_state(self.jet_test)
        self.assertEqual(
            self.jet_test.state_id,
            self.state_stopped,
            "Jet should be set to manager-level state by manager",
        )

    def test_set_state_success_root_level(self):
        """
        Test set_state succeeds when root has sufficient access level.
        Root (level 3) can set state with level 3.
        """
        # Use existing state and set it to Root access level (3)
        self.state_error.access_level = "3"
        self.state_error.invalidate_recordset(["access_level"])

        # Set jet to running state (which has action to error)
        self.jet_test.state_id = self.state_running

        # Root should be able to set state
        self.state_error.with_user(self.root).with_context(
            cetmix_tower_no_commit=True
        ).set_state(self.jet_test)
        self.assertEqual(
            self.jet_test.state_id,
            self.state_error,
            "Jet should be set to root-level state by root",
        )

    def test_set_state_access_error_user_to_manager(self):
        """
        Test set_state raises AccessError when user (level 1)
        tries to set manager-level state (level 2).
        """
        # Use existing state and set it to Manager access level (2)
        self.state_stopped.access_level = "2"
        self.state_stopped.invalidate_recordset(["access_level"])

        # Ensure user has access to the jet and server (for the access check to work)
        self.jet_test.write({"user_ids": [(4, self.user.id)]})
        self.server_test_1.write({"user_ids": [(4, self.user.id)]})

        # Set jet to running state (which has action to stopped)
        self.jet_test.state_id = self.state_running

        # User should not be able to set manager-level state
        with self.assertRaises(AccessError) as context:
            self.state_stopped.with_user(self.user).with_context(
                cetmix_tower_no_commit=True
            ).set_state(self.jet_test)

        self.assertIn(
            "You are not allowed to set the",
            str(context.exception),
            "Should raise AccessError with appropriate message",
        )
        self.assertIn(
            self.state_stopped.name,
            str(context.exception),
            "Error message should include state name",
        )

    def test_set_state_access_error_user_to_root(self):
        """
        Test set_state raises AccessError when user (level 1)
        tries to set root-level state (level 3).
        """
        # Use existing state and set it to Root access level (3)
        self.state_error.access_level = "3"
        self.state_error.invalidate_recordset(["access_level"])

        # Ensure user has access to the jet and server (for the access check to work)
        self.jet_test.write({"user_ids": [(4, self.user.id)]})
        self.server_test_1.write({"user_ids": [(4, self.user.id)]})

        # Set jet to running state (which has action to error)
        self.jet_test.state_id = self.state_running

        # User should not be able to set root-level state
        with self.assertRaises(AccessError) as context:
            self.state_error.with_user(self.user).with_context(
                cetmix_tower_no_commit=True
            ).set_state(self.jet_test)

        self.assertIn(
            "You are not allowed to set the",
            str(context.exception),
            "Should raise AccessError with appropriate message",
        )
        self.assertIn(
            self.state_error.name,
            str(context.exception),
            "Error message should include state name",
        )

    def test_set_state_access_error_manager_to_root(self):
        """
        Test set_state raises AccessError when manager (level 2)
        tries to set root-level state (level 3).
        """
        # Use existing state and set it to Root access level (3)
        self.state_error.access_level = "3"
        self.state_error.invalidate_recordset(["access_level"])

        # Ensure manager has access to the jet and server (for the access check to work)
        self.jet_test.write({"manager_ids": [(4, self.manager.id)]})
        self.server_test_1.write({"manager_ids": [(4, self.manager.id)]})

        # Set jet to running state (which has action to error)
        self.jet_test.state_id = self.state_running

        # Manager should not be able to set root-level state
        with self.assertRaises(AccessError) as context:
            self.state_error.with_user(self.manager).with_context(
                cetmix_tower_no_commit=True
            ).set_state(self.jet_test)

        self.assertIn(
            "You are not allowed to set the",
            str(context.exception),
            "Should raise AccessError with appropriate message",
        )
        self.assertIn(
            self.state_error.name,
            str(context.exception),
            "Error message should include state name",
        )

    def test_set_state_manager_can_access_user_level(self):
        """
        Test set_state succeeds when manager (level 2) who IS in manager_ids
        accesses user-level state (level 1).
        Higher access levels can access lower level states.
        """
        # Use existing state and set it to User access level (1)
        self.state_running.access_level = "1"
        self.state_running.invalidate_recordset(["access_level"])

        # Ensure manager has access to the jet and server
        # Manager IS in manager_ids, so they keep their manager access level (2)
        self.jet_test.write({"manager_ids": [(4, self.manager.id)]})
        self.server_test_1.write({"manager_ids": [(4, self.manager.id)]})

        # Set jet to initial state
        self.jet_test.state_id = self.state_initial

        # Manager should be able to set user-level state
        self.state_running.with_user(self.manager).with_context(
            cetmix_tower_no_commit=True
        ).set_state(self.jet_test)
        self.assertEqual(
            self.jet_test.state_id,
            self.state_running,
            "Manager should be able to set user-level state",
        )

    def test_set_state_manager_not_in_manager_ids_treated_as_user(self):
        """
        Test set_state treats manager (level 2) who is NOT in manager_ids
        as user (level 1).
        Manager should be able to set user-level state but not manager-level state.
        """
        # Use existing state and set it to User access level (1)
        self.state_running.access_level = "1"
        self.state_running.invalidate_recordset(["access_level"])

        # Ensure manager has access to the jet and server via user_ids
        # but NOT via manager_ids
        self.jet_test.write({"user_ids": [(4, self.manager.id)]})
        self.server_test_1.write({"user_ids": [(4, self.manager.id)]})
        # Explicitly ensure manager is NOT in manager_ids
        self.jet_test.write({"manager_ids": [(5, 0, 0)]})

        # Set jet to initial state
        self.jet_test.state_id = self.state_initial

        # Manager (treated as user) should be able to set user-level state
        self.state_running.with_user(self.manager).with_context(
            cetmix_tower_no_commit=True
        ).set_state(self.jet_test)
        self.assertEqual(
            self.jet_test.state_id,
            self.state_running,
            "Manager not in manager_ids should be able to set user-level state",
        )

    def test_set_state_manager_not_in_manager_ids_cannot_access_manager_level(self):
        """
        Test set_state raises AccessError when manager (level 2) who is NOT
        in manager_ids tries to set manager-level state (level 2).
        Manager should be treated as user (level 1) and cannot access level 2.
        """
        # Use existing state and set it to Manager access level (2)
        self.state_stopped.access_level = "2"
        self.state_stopped.invalidate_recordset(["access_level"])

        # Ensure manager has access to the jet and server via user_ids
        # but NOT via manager_ids
        self.jet_test.write({"user_ids": [(4, self.manager.id)]})
        self.server_test_1.write({"user_ids": [(4, self.manager.id)]})
        # Explicitly ensure manager is NOT in manager_ids
        self.jet_test.write({"manager_ids": [(5, 0, 0)]})

        # Set jet to running state (which has action to stopped)
        self.jet_test.state_id = self.state_running

        # Manager (treated as user) should not be able to set manager-level state
        with self.assertRaises(AccessError) as context:
            self.state_stopped.with_user(self.manager).with_context(
                cetmix_tower_no_commit=True
            ).set_state(self.jet_test)

        self.assertIn(
            "You are not allowed to set the",
            str(context.exception),
            "Should raise AccessError with appropriate message",
        )
        self.assertIn(
            self.state_stopped.name,
            str(context.exception),
            "Error message should include state name",
        )

    def test_set_state_root_can_access_manager_level(self):
        """
        Test set_state succeeds when root (level 3)
        accesses manager-level state (level 2).
        Higher access levels can access lower level states.
        """
        # Use existing state and set it to Manager access level (2)
        self.state_stopped.access_level = "2"
        self.state_stopped.invalidate_recordset(["access_level"])

        # Set jet to running state (which has action to stopped)
        self.jet_test.state_id = self.state_running

        # Root should be able to set manager-level state
        self.state_stopped.with_user(self.root).with_context(
            cetmix_tower_no_commit=True
        ).set_state(self.jet_test)
        self.assertEqual(
            self.jet_test.state_id,
            self.state_stopped,
            "Root should be able to set manager-level state",
        )

    def test_set_state_with_context_jet_id(self):
        """
        Test set_state retrieves jet from context when jet parameter is None.
        """
        # Use existing state and set it to User access level (1)
        self.state_running.access_level = "1"
        self.state_running.invalidate_recordset(["access_level"])

        # Ensure user has access to the jet and server
        self.jet_test.write({"user_ids": [(4, self.user.id)]})
        self.server_test_1.write({"user_ids": [(4, self.user.id)]})

        # Set jet to initial state
        self.jet_test.state_id = self.state_initial

        # Set state using context instead of direct parameter
        self.state_running.with_user(self.user).with_context(
            jet_id=self.jet_test.id,
            cetmix_tower_no_commit=True,
        ).set_state()
        self.assertEqual(
            self.jet_test.state_id,
            self.state_running,
            "Jet should be set to state using context jet_id",
        )

    def test_set_state_no_jet_in_context_returns_silently(self):
        """
        Test set_state returns silently when no jet_id in context
        and jet parameter is None.
        """
        # Use existing state
        self.state_running.access_level = "1"
        self.state_running.invalidate_recordset(["access_level"])

        # Call set_state without jet parameter and without context
        # Should return silently without raising exception
        result = (
            self.state_running.with_user(self.user)
            .with_context(cetmix_tower_no_commit=True)
            .set_state()
        )
        self.assertIsNone(result, "Should return None when no jet in context")

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   unlink Tests
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def test_unlink_success_when_not_used_in_action(self):
        """
        Test unlink succeeds when state is not used in any action.
        """
        # Create a state that is not used in any action
        unused_state = self.JetState.create(
            {
                "name": "Unused State",
                "reference": "unused_state",
                "sequence": 100,
            }
        )
        state_id = unused_state.id

        # Unlink should succeed
        unused_state.unlink()

        # Verify state is deleted
        self.assertFalse(
            self.JetState.search([("id", "=", state_id)]),
            "State should be deleted when not used in any action",
        )

    def test_unlink_fails_when_used_as_state_from(self):
        """
        Test unlink raises ValidationError when state is used as state_from_id
        in an action.
        """
        # state_running is used as state_from_id in action_running_to_stopped
        with self.assertRaises(ValidationError) as context:
            self.state_running.unlink()

        error_message = str(context.exception)
        self.assertIn(
            "Some states are still used in the following actions",
            error_message,
            "Should raise ValidationError with appropriate message",
        )
        self.assertIn(
            self.action_running_to_stopped.name,
            error_message,
            "Error message should include action name",
        )
        self.assertIn(
            self.jet_template_test.name,
            error_message,
            "Error message should include template name",
        )

    def test_unlink_fails_when_used_as_state_to(self):
        """
        Test unlink raises ValidationError when state is used as state_to_id
        in an action.
        """
        # state_stopped is used as state_to_id in action_running_to_stopped
        with self.assertRaises(ValidationError) as context:
            self.state_stopped.unlink()

        error_message = str(context.exception)
        self.assertIn(
            "Some states are still used in the following actions",
            error_message,
            "Should raise ValidationError with appropriate message",
        )
        self.assertIn(
            self.action_running_to_stopped.name,
            error_message,
            "Error message should include action name",
        )
        self.assertIn(
            self.jet_template_test.name,
            error_message,
            "Error message should include template name",
        )

    def test_unlink_fails_when_used_as_state_transit(self):
        """
        Test unlink raises ValidationError when state is used as state_transit_id
        in an action.
        """
        # state_stopping is used as state_transit_id in action_running_to_stopped
        with self.assertRaises(ValidationError) as context:
            self.state_stopping.unlink()

        error_message = str(context.exception)
        self.assertIn(
            "Some states are still used in the following actions",
            error_message,
            "Should raise ValidationError with appropriate message",
        )
        self.assertIn(
            self.action_running_to_stopped.name,
            error_message,
            "Error message should include action name",
        )
        self.assertIn(
            self.jet_template_test.name,
            error_message,
            "Error message should include template name",
        )

    def test_unlink_fails_with_multiple_actions(self):
        """
        Test unlink raises ValidationError with multiple actions when state
        is used in multiple actions.
        """
        # state_running is used in multiple actions:
        # - action_running_to_stopped (state_from_id)
        # - action_stopped_to_running (state_to_id)
        # - action_running_to_error (state_from_id)
        # - action_initial_to_running (state_to_id)
        with self.assertRaises(ValidationError) as context:
            self.state_running.unlink()

        error_message = str(context.exception)
        self.assertIn(
            "Some states are still used in the following actions",
            error_message,
            "Should raise ValidationError with appropriate message",
        )
        # Verify multiple actions are mentioned
        self.assertIn(
            self.action_running_to_stopped.name,
            error_message,
            "Error message should include first action name",
        )
        self.assertIn(
            self.jet_template_test.name,
            error_message,
            "Error message should include template name",
        )

    def test_unlink_fails_with_multiple_states(self):
        """
        Test unlink raises ValidationError when trying to unlink multiple states
        where at least one is used in an action.
        """
        # Create an unused state
        unused_state = self.JetState.create(
            {
                "name": "Another Unused State",
                "reference": "another_unused_state",
                "sequence": 101,
            }
        )

        # Try to unlink both unused_state and state_running (which is used)
        states_to_unlink = unused_state | self.state_running
        with self.assertRaises(ValidationError) as context:
            states_to_unlink.unlink()

        error_message = str(context.exception)
        self.assertIn(
            "Some states are still used in the following actions",
            error_message,
            "Should raise ValidationError with appropriate message",
        )
        # Verify that neither state was deleted
        self.assertTrue(
            unused_state.exists(),
            "Unused state should not be deleted when another state fails",
        )
        self.assertTrue(
            self.state_running.exists(),
            "Used state should not be deleted",
        )
