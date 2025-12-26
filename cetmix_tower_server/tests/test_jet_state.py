# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError

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

        # Set jet to initial state
        self.jet_test.state_id = self.state_initial

        # User should be able to set state
        self.state_running.with_user(self.user).set_state(self.jet_test)
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

        # Set jet to running state (which has action to stopped)
        self.jet_test.state_id = self.state_running

        # Manager should be able to set state
        self.state_stopped.with_user(self.manager).set_state(self.jet_test)
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

        # Set jet to running state (which has action to error)
        self.jet_test.state_id = self.state_running

        # Root should be able to set state
        self.state_error.with_user(self.root).set_state(self.jet_test)
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

        # Set jet to running state (which has action to stopped)
        self.jet_test.state_id = self.state_running

        # User should not be able to set manager-level state
        with self.assertRaises(AccessError) as context:
            self.state_stopped.with_user(self.user).set_state(self.jet_test)

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

        # Set jet to running state (which has action to error)
        self.jet_test.state_id = self.state_running

        # User should not be able to set root-level state
        with self.assertRaises(AccessError) as context:
            self.state_error.with_user(self.user).set_state(self.jet_test)

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

        # Set jet to running state (which has action to error)
        self.jet_test.state_id = self.state_running

        # Manager should not be able to set root-level state
        with self.assertRaises(AccessError) as context:
            self.state_error.with_user(self.manager).set_state(self.jet_test)

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
        Test set_state succeeds when manager (level 2)
        accesses user-level state (level 1).
        Higher access levels can access lower level states.
        """
        # Use existing state and set it to User access level (1)
        self.state_running.access_level = "1"

        # Set jet to initial state
        self.jet_test.state_id = self.state_initial

        # Manager should be able to set user-level state
        self.state_running.with_user(self.manager).set_state(self.jet_test)
        self.assertEqual(
            self.jet_test.state_id,
            self.state_running,
            "Manager should be able to set user-level state",
        )

    def test_set_state_root_can_access_manager_level(self):
        """
        Test set_state succeeds when root (level 3)
        accesses manager-level state (level 2).
        Higher access levels can access lower level states.
        """
        # Use existing state and set it to Manager access level (2)
        self.state_stopped.access_level = "2"

        # Set jet to running state (which has action to stopped)
        self.jet_test.state_id = self.state_running

        # Root should be able to set manager-level state
        self.state_stopped.with_user(self.root).set_state(self.jet_test)
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

        # Set jet to initial state
        self.jet_test.state_id = self.state_initial

        # Set state using context instead of direct parameter
        self.state_running.with_user(self.user).with_context(
            jet_id=self.jet_test.id
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

        # Call set_state without jet parameter and without context
        # Should return silently without raising exception
        result = self.state_running.with_user(self.user).set_state()
        self.assertIsNone(result, "Should return None when no jet in context")
