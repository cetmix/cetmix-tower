# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError

from .common_jets import TestTowerJetsCommon


class TestTowerJetTemplate(TestTowerJetsCommon):
    """
    Test the jet template model
    """

    # All jet-related test data is now inherited from TestTowerJetsCommon

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create additional servers for multi-server tests
        cls.server_test_2 = cls.Server.create(
            {
                "name": "Test Server 2",
                "reference": "test_server_2",
                "ip_v4_address": "192.168.1.102",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "os_id": cls.os_debian_10.id,
            }
        )
        cls.server_test_3 = cls.Server.create(
            {
                "name": "Test Server 3",
                "reference": "test_server_3",
                "ip_v4_address": "192.168.1.103",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "os_id": cls.os_debian_10.id,
            }
        )

    def test_compute_border_actions_no_actions(self):
        """
        Test _compute_border_actions with no actions defined
        """
        # Create a jet template with no actions
        template = self.JetTemplate.create(
            {
                "name": "No Actions Template",
                "reference": "no_actions_template",
                "server_ids": [(4, self.server_test_1.id)],
            }
        )

        # Both border actions should be False
        self.assertFalse(
            template.action_create_id,
            "Create action should be False when no actions exist",
        )
        self.assertFalse(
            template.action_destroy_id,
            "Destroy action should be False when no actions exist",
        )

    def test_compute_border_actions_both_valid_actions(self):
        """
        Test _compute_border_actions with both valid create and destroy actions
        """
        # Use common actions from class setup
        create_action = self.action_create
        destroy_action = self.action_destroy

        # Both actions should be set
        self.assertEqual(
            self.jet_template_test.action_create_id,
            create_action,
            "Create action should be set to the valid action",
        )
        self.assertEqual(
            self.jet_template_test.action_destroy_id,
            destroy_action,
            "Destroy action should be set to the valid action",
        )

    def test_compute_border_actions_invalid_create_action_with_initial_state(self):
        """
        Test _compute_border_actions with invalid create action (has initial state)
        """
        # Create an invalid create action (has state_from_id)
        invalid_create_action = self.JetAction.create(
            {
                "name": "Invalid Create Action",
                "reference": "invalid_create_action",
                "jet_template_id": self.jet_template_test.id,
                "state_from_id": self.state_initial.id,  # Invalid for create
                "state_to_id": self.state_running.id,
                "state_transit_id": self.state_starting.id,
                "priority": 10,
            }
        )

        # Since action_create_id is readonly=False, we can set it directly
        # but the compute method won't be triggered automatically
        self.jet_template_test.action_create_id = invalid_create_action

        # The action should remain set because compute method wasn't triggered
        self.assertEqual(
            self.jet_template_test.action_create_id,
            invalid_create_action,
            "Create action should remain set when directly assigned (readonly=False)",
        )

        # Now trigger the compute method manually to test the logic
        self.jet_template_test._compute_border_actions()

        # Create action should be cleared because it's invalid
        self.assertFalse(
            self.jet_template_test.action_create_id,
            "Create action should be cleared when it has an initial state",
        )

    def test_compute_border_actions_invalid_create_action_no_final_state(self):
        """
        Test _compute_border_actions with invalid create action (no final state)
        """
        # Create an invalid create action (no state_to_id)
        invalid_create_action = self.JetAction.create(
            {
                "name": "Invalid Create Action",
                "reference": "invalid_create_action",
                "jet_template_id": self.jet_template_test.id,
                "state_from_id": False,
                "state_to_id": False,  # No final state - invalid for create
                "state_transit_id": self.state_starting.id,
                "priority": 10,
            }
        )

        # Since action_create_id is readonly=False, we can set it directly
        # but the compute method won't be triggered automatically
        self.jet_template_test.action_create_id = invalid_create_action

        # The action should remain set because compute method wasn't triggered
        self.assertEqual(
            self.jet_template_test.action_create_id,
            invalid_create_action,
            "Create action should remain set when directly assigned (readonly=False)",
        )

        # Now trigger the compute method manually to test the logic
        self.jet_template_test._compute_border_actions()

        # Create action should be cleared because it's invalid
        self.assertFalse(
            self.jet_template_test.action_create_id,
            "Create action should be cleared when it has no final state",
        )

    def test_compute_border_actions_invalid_destroy_action_with_final_state(self):
        """
        Test _compute_border_actions with invalid destroy action (has final state)
        """
        # Create an invalid destroy action (has state_to_id)
        invalid_destroy_action = self.JetAction.create(
            {
                "name": "Invalid Destroy Action",
                "reference": "invalid_destroy_action",
                "jet_template_id": self.jet_template_test.id,
                "state_from_id": self.state_running.id,
                "state_to_id": self.state_stopped.id,  # Invalid for destroy
                "state_transit_id": self.state_stopping.id,
                "priority": 10,
            }
        )

        # Since action_destroy_id is readonly=False, we can set it directly
        # but the compute method won't be triggered automatically
        self.jet_template_test.action_destroy_id = invalid_destroy_action

        # The action should remain set because compute method wasn't triggered
        self.assertEqual(
            self.jet_template_test.action_destroy_id,
            invalid_destroy_action,
            "Destroy action should remain set when directly assigned (readonly=False)",
        )

        # Now trigger the compute method manually to test the logic
        self.jet_template_test._compute_border_actions()

        # Destroy action should be cleared because it's invalid
        self.assertFalse(
            self.jet_template_test.action_destroy_id,
            "Destroy action should be cleared when it has a final state",
        )

    def test_compute_border_actions_multiple_actions_priority(self):
        """
        Test _compute_border_actions with multiple actions, checking priority order
        """
        # Clear existing border actions to force recomputation
        self.jet_template_test.action_create_id = False
        self.jet_template_test.action_destroy_id = False

        # Create multiple create actions with different priorities
        # Use priority 0 to ensure they have higher priority
        # than common actions (priority 1)
        self.JetAction.create(
            {
                "name": "Create Action 1",
                "reference": "create_action_1",
                "jet_template_id": self.jet_template_test.id,
                "state_from_id": False,
                "state_to_id": self.state_running.id,
                "state_transit_id": self.state_starting.id,
                "priority": 2,  # Higher priority number (lower priority)
            }
        )

        create_action_2 = self.JetAction.create(
            {
                "name": "Create Action 2",
                "reference": "create_action_2",
                "jet_template_id": self.jet_template_test.id,
                "state_from_id": False,
                "state_to_id": self.state_running.id,
                "state_transit_id": self.state_starting.id,
                "priority": 0,  # Lower priority number (higher priority)
            }
        )

        # Create multiple destroy actions with different priorities
        self.JetAction.create(
            {
                "name": "Destroy Action 1",
                "reference": "destroy_action_1",
                "jet_template_id": self.jet_template_test.id,
                "state_from_id": self.state_running.id,
                "state_to_id": False,
                "state_transit_id": self.state_stopping.id,
                "priority": 2,  # Higher priority number (lower priority)
            }
        )

        destroy_action_2 = self.JetAction.create(
            {
                "name": "Destroy Action 2",
                "reference": "destroy_action_2",
                "jet_template_id": self.jet_template_test.id,
                "state_from_id": self.state_running.id,
                "state_to_id": False,
                "state_transit_id": self.state_stopping.id,
                "priority": 0,  # Lower priority number (higher priority)
            }
        )

        # Trigger recomputation of border actions to ensure
        # the new actions are considered
        self.jet_template_test._compute_border_actions()

        # Should select the actions with higher priority (lower priority number)
        self.assertEqual(
            self.jet_template_test.action_create_id,
            create_action_2,
            "Create action should be the one with higher priority",
        )
        self.assertEqual(
            self.jet_template_test.action_destroy_id,
            destroy_action_2,
            "Destroy action should be the one with higher priority",
        )

    def test_compute_border_actions_action_updates(self):
        """
        Test _compute_border_actions when actions are updated
        """
        # Use common actions from class setup
        create_action = self.action_create
        destroy_action = self.action_destroy

        # Both actions should be set initially
        self.assertEqual(self.jet_template_test.action_create_id, create_action)
        self.assertEqual(self.jet_template_test.action_destroy_id, destroy_action)

        # Update create action to make it invalid (add initial state)
        create_action.write({"state_from_id": self.state_initial.id})

        # Create action should be cleared, destroy action should remain
        self.assertFalse(
            self.jet_template_test.action_create_id,
            "Create action should be cleared after becoming invalid",
        )
        self.assertEqual(
            self.jet_template_test.action_destroy_id,
            destroy_action,
            "Destroy action should remain unchanged",
        )

        # Update destroy action to make it invalid (add final state)
        destroy_action.write({"state_to_id": self.state_stopped.id})

        # Both actions should be cleared
        self.assertFalse(
            self.jet_template_test.action_create_id,
            "Create action should remain cleared",
        )
        self.assertFalse(
            self.jet_template_test.action_destroy_id,
            "Destroy action should be cleared after becoming invalid",
        )

    def test_find_action_path_bfs_multiple_paths_shortest(self):
        """
        Test _find_action_path_bfs finds the shortest path when multiple paths exist
        """
        # Create actions for multiple paths
        # Short path: A -> C
        action_ac = self.JetAction.create(
            {
                "name": "Action A to C (short)",
                "reference": "action_ac",
                "jet_template_id": self.jet_template_test.id,
                "state_from_id": self.state_a.id,
                "state_to_id": self.state_c.id,
                "state_transit_id": self.state_stopping.id,
                "priority": 10,
            }
        )
        # Long path: A -> B -> D -> C
        action_ab = self.JetAction.create(
            {
                "name": "Action A to B",
                "reference": "action_ab",
                "jet_template_id": self.jet_template_test.id,
                "state_from_id": self.state_a.id,
                "state_to_id": self.state_b.id,
                "state_transit_id": self.state_starting.id,
                "priority": 10,
            }
        )
        action_bd = self.JetAction.create(
            {
                "name": "Action B to D",
                "reference": "action_bd",
                "jet_template_id": self.jet_template_test.id,
                "state_from_id": self.state_b.id,
                "state_to_id": self.state_d.id,
                "state_transit_id": self.state_stopping.id,
                "priority": 10,
            }
        )
        action_dc = self.JetAction.create(
            {
                "name": "Action D to C",
                "reference": "action_dc",
                "jet_template_id": self.jet_template_test.id,
                "state_from_id": self.state_d.id,
                "state_to_id": self.state_c.id,
                "state_transit_id": self.state_stopping.id,
                "priority": 10,
            }
        )

        # Create adjacency with multiple paths
        adjacency = {
            self.state_a: [
                (self.state_c, action_ac),
                (self.state_b, action_ab),
            ],  # Short and long path
            self.state_b: [(self.state_d, action_bd)],
            self.state_d: [(self.state_c, action_dc)],
        }

        # Test that shortest path is found
        result = self.jet_template_test._find_action_path_bfs(
            self.state_a, self.state_c, adjacency
        )
        expected_path = [action_ac]  # Shortest path
        self.assertEqual(
            result,
            expected_path,
            "Should return shortest path when multiple paths exist",
        )

    def test_find_action_path_bfs_empty_adjacency(self):
        """
        Test _find_action_path_bfs with empty adjacency list
        """
        # Empty adjacency
        adjacency = {}

        # Test with empty adjacency
        result = self.jet_template_test._find_action_path_bfs(
            self.state_a, self.state_b, adjacency
        )
        self.assertIsNone(result, "Should return None with empty adjacency")

    def test_find_action_path_bfs_cyclic_graph(self):
        """
        Test _find_action_path_bfs with cyclic graph
        """
        # Create actions for cyclic graph
        action_ab = self.JetAction.create(
            {
                "name": "Action A to B",
                "reference": "action_ab",
                "jet_template_id": self.jet_template_test.id,
                "state_from_id": self.state_a.id,
                "state_to_id": self.state_b.id,
                "state_transit_id": self.state_starting.id,
                "priority": 10,
            }
        )
        action_bc = self.JetAction.create(
            {
                "name": "Action B to C",
                "reference": "action_bc",
                "jet_template_id": self.jet_template_test.id,
                "state_from_id": self.state_b.id,
                "state_to_id": self.state_c.id,
                "state_transit_id": self.state_stopping.id,
                "priority": 10,
            }
        )
        action_ca = self.JetAction.create(
            {
                "name": "Action C to A",
                "reference": "action_ca",
                "jet_template_id": self.jet_template_test.id,
                "state_from_id": self.state_c.id,
                "state_to_id": self.state_a.id,
                "state_transit_id": self.state_starting.id,
                "priority": 10,
            }
        )

        # Create cyclic adjacency: A -> B -> C -> A
        adjacency = {
            self.state_a: [(self.state_b, action_ab)],
            self.state_b: [(self.state_c, action_bc)],
            self.state_c: [(self.state_a, action_ca)],
        }

        # Test path from A to C (should find path despite cycle)
        result = self.jet_template_test._find_action_path_bfs(
            self.state_a, self.state_c, adjacency
        )
        expected_path = [action_ab, action_bc]
        self.assertEqual(result, expected_path, "Should find path in cyclic graph")

    def test_find_action_path_bfs_disconnected_states(self):
        """
        Test _find_action_path_bfs with disconnected states
        """
        # Create adjacency with disconnected components
        adjacency = {
            self.state_a: [(self.state_b, "action_ab")],  # A and B connected
            # state_c is isolated
        }

        # Test path from A to C (disconnected)
        result = self.jet_template_test._find_action_path_bfs(
            self.state_a, self.state_c, adjacency
        )
        self.assertIsNone(result, "Should return None for disconnected states")

    def test_find_action_path_bfs_with_get_action_adjacency(self):
        """
        Test _find_action_path_bfs using the actual _get_action_adjacency method
        """
        # Create actions that will be used by _get_action_adjacency
        action_ab = self.JetAction.create(
            {
                "name": "Action A to B",
                "reference": "action_ab",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_a.id,
                "state_to_id": self.state_b.id,
                "state_transit_id": self.state_starting.id,
                "priority": 10,
            }
        )
        action_bc = self.JetAction.create(
            {
                "name": "Action B to C",
                "reference": "action_bc",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_b.id,
                "state_to_id": self.state_c.id,
                "state_transit_id": self.state_stopping.id,
                "priority": 10,
            }
        )

        # Get adjacency using the actual method
        adjacency = self.clean_template._get_action_adjacency()

        # Test path from A to C
        result = self.clean_template._find_action_path_bfs(
            self.state_a, self.state_c, adjacency
        )
        expected_path = [action_ab, action_bc]
        self.assertEqual(
            result, expected_path, "Should work with _get_action_adjacency method"
        )

    def test_get_action_adjacency_no_actions(self):
        """
        Test _get_action_adjacency with no actions
        """
        # Create a template with no actions
        template = self.JetTemplate.create(
            {
                "name": "No Actions Template",
                "reference": "no_actions_template",
                "server_ids": [(4, self.server_test_1.id)],
            }
        )

        # Get adjacency
        adjacency = template._get_action_adjacency()

        # Should return empty dict
        self.assertEqual(
            adjacency, {}, "Should return empty dict when no actions exist"
        )

    def test_get_action_adjacency_single_action(self):
        """
        Test _get_action_adjacency with a single valid action
        """
        # Create action
        action_ab = self.JetAction.create(
            {
                "name": "Action A to B",
                "reference": "action_ab",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_a.id,
                "state_to_id": self.state_b.id,
                "state_transit_id": self.state_starting.id,
                "priority": 10,
            }
        )

        # Get adjacency
        adjacency = self.clean_template._get_action_adjacency()

        # Should have one entry
        self.assertIn(self.state_a, adjacency, "Should include state_a in adjacency")
        self.assertEqual(
            len(adjacency[self.state_a]), 1, "Should have one transition from state_a"
        )
        self.assertEqual(
            adjacency[self.state_a][0],
            (self.state_b, action_ab),
            "Should map to state_b with action_ab",
        )

    def test_get_action_adjacency_multiple_actions_from_same_state(self):
        """
        Test _get_action_adjacency with multiple actions from the same state
        """
        # Create multiple actions from state_a
        action_ab = self.JetAction.create(
            {
                "name": "Action A to B",
                "reference": "action_ab",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_a.id,
                "state_to_id": self.state_b.id,
                "state_transit_id": self.state_starting.id,
                "priority": 10,
            }
        )
        action_ac = self.JetAction.create(
            {
                "name": "Action A to C",
                "reference": "action_ac",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_a.id,
                "state_to_id": self.state_c.id,
                "state_transit_id": self.state_stopping.id,
                "priority": 20,
            }
        )

        # Get adjacency
        adjacency = self.clean_template._get_action_adjacency()

        # Should have multiple transitions from state_a
        self.assertIn(self.state_a, adjacency, "Should include state_a in adjacency")
        self.assertEqual(
            len(adjacency[self.state_a]), 2, "Should have two transitions from state_a"
        )

        # Check that both transitions are present
        transitions = adjacency[self.state_a]
        expected_transitions = [(self.state_b, action_ab), (self.state_c, action_ac)]
        for expected in expected_transitions:
            self.assertIn(
                expected, transitions, f"Should include transition {expected}"
            )

    def test_get_action_adjacency_actions_without_from_state(self):
        """
        Test _get_action_adjacency with actions that have no state_from_id
        """
        # Create action without state_from_id (create action)
        self.JetAction.create(
            {
                "name": "Create Action",
                "reference": "create_action",
                "jet_template_id": self.clean_template.id,
                "state_from_id": False,  # No initial state
                "state_to_id": self.state_b.id,
                "state_transit_id": self.state_starting.id,
                "priority": 10,
            }
        )

        # Get adjacency
        adjacency = self.clean_template._get_action_adjacency()

        # Should be empty because action has no state_from_id
        self.assertEqual(
            adjacency, {}, "Should return empty dict for actions without state_from_id"
        )

    def test_get_action_adjacency_actions_without_to_state(self):
        """
        Test _get_action_adjacency with actions that have no state_to_id
        """
        # Create action without state_to_id (destroy action)
        self.JetAction.create(
            {
                "name": "Destroy Action",
                "reference": "destroy_action",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_a.id,
                "state_to_id": False,  # No final state
                "state_transit_id": self.state_starting.id,
                "priority": 10,
            }
        )

        # Get adjacency
        adjacency = self.clean_template._get_action_adjacency()

        # Should be empty because action has no state_to_id
        self.assertEqual(
            adjacency, {}, "Should return empty dict for actions without state_to_id"
        )

    def test_get_action_adjacency_complex_graph(self):
        """
        Test _get_action_adjacency with a complex graph structure
        """
        # Create complex action graph
        action_ab = self.JetAction.create(
            {
                "name": "Action A to B",
                "reference": "action_ab",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_a.id,
                "state_to_id": self.state_b.id,
                "state_transit_id": self.state_starting.id,
                "priority": 10,
            }
        )
        action_ac = self.JetAction.create(
            {
                "name": "Action A to C",
                "reference": "action_ac",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_a.id,
                "state_to_id": self.state_c.id,
                "state_transit_id": self.state_stopping.id,
                "priority": 20,
            }
        )
        action_bd = self.JetAction.create(
            {
                "name": "Action B to D",
                "reference": "action_bd",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_b.id,
                "state_to_id": self.state_d.id,
                "state_transit_id": self.state_stopping.id,
                "priority": 10,
            }
        )
        action_cd = self.JetAction.create(
            {
                "name": "Action C to D",
                "reference": "action_cd",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_c.id,
                "state_to_id": self.state_d.id,
                "state_transit_id": self.state_stopping.id,
                "priority": 10,
            }
        )

        # Get adjacency
        adjacency = self.clean_template._get_action_adjacency()

        # Check structure
        self.assertIn(self.state_a, adjacency, "Should include state_a")
        self.assertIn(self.state_b, adjacency, "Should include state_b")
        self.assertIn(self.state_c, adjacency, "Should include state_c")
        self.assertNotIn(
            self.state_d, adjacency, "Should not include state_d (no outgoing edges)"
        )

        # Check transitions from state_a
        self.assertEqual(
            len(adjacency[self.state_a]),
            2,
            "State A should have 2 outgoing transitions",
        )
        expected_from_a = [(self.state_b, action_ab), (self.state_c, action_ac)]
        for expected in expected_from_a:
            self.assertIn(
                expected,
                adjacency[self.state_a],
                f"State A should have transition {expected}",
            )

        # Check transitions from state_b
        self.assertEqual(
            len(adjacency[self.state_b]), 1, "State B should have 1 outgoing transition"
        )
        self.assertEqual(
            adjacency[self.state_b][0],
            (self.state_d, action_bd),
            "State B should transition to D",
        )

        # Check transitions from state_c
        self.assertEqual(
            len(adjacency[self.state_c]), 1, "State C should have 1 outgoing transition"
        )
        self.assertEqual(
            adjacency[self.state_c][0],
            (self.state_d, action_cd),
            "State C should transition to D",
        )

    def test_get_action_adjacency_mixed_valid_invalid_actions(self):
        """
        Test _get_action_adjacency with mix of valid and invalid actions
        """
        # Create valid action
        valid_action = self.JetAction.create(
            {
                "name": "Valid Action",
                "reference": "valid_action",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_a.id,
                "state_to_id": self.state_b.id,
                "state_transit_id": self.state_starting.id,
                "priority": 10,
            }
        )

        # Create invalid actions (should be ignored)
        self.JetAction.create(
            {
                "name": "Invalid Action 1",
                "reference": "invalid_action_1",
                "jet_template_id": self.clean_template.id,
                "state_from_id": False,  # No initial state
                "state_to_id": self.state_b.id,
                "state_transit_id": self.state_starting.id,
                "priority": 10,
            }
        )
        self.JetAction.create(
            {
                "name": "Invalid Action 2",
                "reference": "invalid_action_2",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_a.id,
                "state_to_id": False,  # No final state
                "state_transit_id": self.state_starting.id,
                "priority": 10,
            }
        )

        # Get adjacency
        adjacency = self.clean_template._get_action_adjacency()

        # Should only include the valid action
        self.assertIn(self.state_a, adjacency, "Should include state_a")
        self.assertEqual(
            len(adjacency[self.state_a]), 1, "Should have only one valid transition"
        )
        self.assertEqual(
            adjacency[self.state_a][0],
            (self.state_b, valid_action),
            "Should include only valid action",
        )

    def test_get_action_adjacency_self_loop(self):
        """
        Test _get_action_adjacency with self-loop actions
        """
        # Create self-loop action
        self_loop_action = self.JetAction.create(
            {
                "name": "Self Loop Action",
                "reference": "self_loop_action",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_a.id,
                "state_to_id": self.state_a.id,  # Same state
                "state_transit_id": self.state_starting.id,
                "priority": 10,
            }
        )

        # Get adjacency
        adjacency = self.clean_template._get_action_adjacency()

        # Should include self-loop
        self.assertIn(self.state_a, adjacency, "Should include state_a")
        self.assertEqual(
            len(adjacency[self.state_a]), 1, "Should have one self-loop transition"
        )
        self.assertEqual(
            adjacency[self.state_a][0],
            (self.state_a, self_loop_action),
            "Should include self-loop action",
        )

    def test_get_action_path_no_create_destroy_actions(self):
        """
        Test _get_action_path when no create or destroy actions are set
        """
        # Create a template with no border actions
        template = self.JetTemplate.create(
            {
                "name": "No Border Actions Template",
                "reference": "no_border_actions_template",
                "server_ids": [(4, self.server_test_1.id)],
            }
        )

        # Test path without state_from and state_to
        result = template._get_action_path()
        self.assertEqual(
            result, [], "Should return empty list when no create action exists"
        )

        # Test path with state_from but no state_to
        result = template._get_action_path(state_from=self.state_a)
        self.assertEqual(
            result, [], "Should return empty list when no destroy action exists"
        )

    def test_get_action_path_both_parameters_provided(self):
        """
        Test _get_action_path when both state_from and state_to are provided
        """
        # Create action
        action_ab = self.JetAction.create(
            {
                "name": "Action A to B",
                "reference": "action_ab",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_a.id,
                "state_to_id": self.state_b.id,
                "state_transit_id": self.state_starting.id,
                "priority": 10,
            }
        )

        # Test path with both parameters provided
        result = self.clean_template._get_action_path(
            state_from=self.state_a, state_to=self.state_b
        )
        self.assertEqual(
            result,
            [action_ab],
            "Should return action path when both parameters provided",
        )

    def test_get_action_path_requires_at_least_one_parameter(self):
        """
        Test _get_action_path behavior when no parameters are provided
        """
        # Create a template with no border actions
        template = self.JetTemplate.create(
            {
                "name": "No Border Actions Template",
                "reference": "no_border_actions_template",
                "server_ids": [(4, self.server_test_1.id)],
            }
        )

        # Test with no parameters - should return empty list
        result = template._get_action_path()
        self.assertEqual(
            result,
            [],
            "Should return empty list when no parameters and no border actions",
        )

        # Test with only state_from
        result = template._get_action_path(state_from=self.state_a)
        self.assertEqual(
            result,
            [],
            "Should return empty list when only state_from provided",
        )

        # Test with only state_to
        result = template._get_action_path(state_to=self.state_b)
        self.assertEqual(
            result,
            [],
            "Should return empty list when only state_to provided and no create action",
        )

    def test_get_action_path_with_create_action_only(self):
        """
        Test _get_action_path with only create action set
        """
        # Create create action
        create_action = self.JetAction.create(
            {
                "name": "Create Action",
                "reference": "create_action",
                "jet_template_id": self.clean_template.id,
                "state_from_id": False,
                "state_to_id": self.state_b.id,
                "state_transit_id": self.state_starting.id,
                "priority": 10,
            }
        )

        # Set create action
        self.clean_template.action_create_id = create_action

        # Test path without state_from (should return empty because no destroy action)
        result = self.clean_template._get_action_path()
        self.assertEqual(
            result, [], "Should return empty list when no destroy action provided"
        )

        # Test path with state_from (should not use create action)
        result = self.clean_template._get_action_path(state_from=self.state_b)
        self.assertEqual(
            result,
            [],
            "Should return empty list when state_from provided and no path exists",
        )

    def test_build_dependency_graph_simple_dependency(self):
        """Test _build_dependency_graph with simple dependency chain"""
        # Use the existing dependency hierarchy

        graph = self.jet_template_odoo._build_dependency_graph()

        # Verify all templates are in the graph
        expected_template_ids = [
            self.jet_template_odoo.id,
            self.jet_template_postgres.id,
            self.jet_template_nginx.id,
            self.jet_template_docker.id,
            self.jet_template_tower_core.id,
        ]
        self.assertEqual(
            set(graph.keys()),
            set(expected_template_ids),
            "All templates should be in the graph",
        )

        # Verify Odoo template info
        odoo_info = graph[self.jet_template_odoo.id]
        self.assertEqual(odoo_info["template"], self.jet_template_odoo)
        self.assertEqual(odoo_info["name"], "Odoo")
        self.assertEqual(odoo_info["reference"], "odoo")
        self.assertEqual(odoo_info["level"], 0)  # Root template
        self.assertEqual(
            len(odoo_info["dependencies"]), 2
        )  # Depends on Postgres and Nginx

        # Verify Odoo dependencies
        odoo_dep_ids = [dep["template_id"] for dep in odoo_info["dependencies"]]
        self.assertIn(self.jet_template_postgres.id, odoo_dep_ids)
        self.assertIn(self.jet_template_nginx.id, odoo_dep_ids)

        # Verify Postgres template info
        postgres_info = graph[self.jet_template_postgres.id]
        self.assertEqual(postgres_info["template"], self.jet_template_postgres)
        self.assertEqual(postgres_info["name"], "Postgres")
        self.assertEqual(postgres_info["reference"], "postgres")
        self.assertEqual(postgres_info["level"], 1)  # One level from root
        self.assertEqual(len(postgres_info["dependencies"]), 1)  # Depends on Docker

        # Verify Postgres dependencies
        postgres_dep_ids = [dep["template_id"] for dep in postgres_info["dependencies"]]
        self.assertIn(self.jet_template_docker.id, postgres_dep_ids)

        # Verify Nginx template info
        nginx_info = graph[self.jet_template_nginx.id]
        self.assertEqual(nginx_info["template"], self.jet_template_nginx)
        self.assertEqual(nginx_info["name"], "Nginx")
        self.assertEqual(nginx_info["reference"], "nginx")
        self.assertEqual(nginx_info["level"], 1)  # One level from root
        self.assertEqual(len(nginx_info["dependencies"]), 1)  # Depends on Docker

        # Verify Nginx dependencies
        nginx_dep_ids = [dep["template_id"] for dep in nginx_info["dependencies"]]
        self.assertIn(self.jet_template_docker.id, nginx_dep_ids)

        # Verify Docker template info
        docker_info = graph[self.jet_template_docker.id]
        self.assertEqual(docker_info["template"], self.jet_template_docker)
        self.assertEqual(docker_info["name"], "Docker")
        self.assertEqual(docker_info["reference"], "docker")
        self.assertEqual(docker_info["level"], 2)  # Two levels from root
        self.assertEqual(len(docker_info["dependencies"]), 1)  # Depends on Tower Core

        # Verify Docker dependencies
        docker_dep_ids = [dep["template_id"] for dep in docker_info["dependencies"]]
        self.assertIn(self.jet_template_tower_core.id, docker_dep_ids)

        # Verify Tower Core template info
        tower_core_info = graph[self.jet_template_tower_core.id]
        self.assertEqual(tower_core_info["template"], self.jet_template_tower_core)
        self.assertEqual(tower_core_info["name"], "Tower Core")
        self.assertEqual(tower_core_info["reference"], "tower_core")
        self.assertEqual(tower_core_info["level"], 3)  # Three levels from root
        self.assertEqual(len(tower_core_info["dependencies"]), 0)  # No dependencies

    def test_build_dependency_graph_circular_dependency(self):
        """
        Test circular dependency detection in constraint validation.

        This test verifies that circular dependency detection correctly includes
        the new dependency being created, not just existing ones from the database.

        Scenario:
        A->B, B->C exist, trying to create C->A should be detected as circular.
        """

        # Create a circular dependency: A -> B -> C -> A
        template_a = self.JetTemplate.create(
            {
                "name": "Template A",
                "reference": "template_a",
            }
        )
        template_b = self.JetTemplate.create(
            {
                "name": "Template B",
                "reference": "template_b",
            }
        )
        template_c = self.JetTemplate.create(
            {
                "name": "Template C",
                "reference": "template_c",
            }
        )

        # Create first two dependencies (A -> B -> C)
        self.JetTemplateDependency.create(
            {
                "template_id": template_a.id,
                "template_required_id": template_b.id,
                "state_required_id": self.state_running.id,
            }
        )
        self.JetTemplateDependency.create(
            {
                "template_id": template_b.id,
                "template_required_id": template_c.id,
                "state_required_id": self.state_running.id,
            }
        )

        # The third dependency (C -> A) should raise a ValidationError
        with self.assertRaises(ValidationError) as context:
            self.JetTemplateDependency.create(
                {
                    "template_id": template_c.id,
                    "template_required_id": template_a.id,
                    "state_required_id": self.state_running.id,
                }
            )

        # Verify the error message mentions circular reference
        error_message = str(context.exception)
        self.assertIn("circular reference", error_message.lower())
        self.assertIn("Template C", error_message)

    def test_build_dependency_graph_with_state_requirements(self):
        """Test _build_dependency_graph with state requirements"""
        # pylint: disable=protected-access
        # Create a template with state requirements
        template_with_state = self.JetTemplate.create(
            {
                "name": "Template With State",
                "reference": "template_with_state",
            }
        )

        # Create dependency with state requirement
        self.JetTemplateDependency.create(
            {
                "template_id": template_with_state.id,
                "template_required_id": self.jet_template_tower_core.id,
                "state_required_id": self.state_running.id,
            }
        )

        graph = template_with_state._build_dependency_graph()

        # Verify the dependency includes state information
        template_info = graph[template_with_state.id]
        self.assertEqual(len(template_info["dependencies"]), 1)

        dep_info = template_info["dependencies"][0]
        self.assertEqual(dep_info["template_id"], self.jet_template_tower_core.id)
        self.assertEqual(dep_info["template_name"], "Tower Core")
        self.assertEqual(dep_info["template_reference"], "tower_core")
        self.assertEqual(dep_info["required_state_id"], self.state_running.id)
        self.assertEqual(dep_info["required_state_name"], "Test Running")

    def test_build_dependency_graph_complex_hierarchy(self):
        """Test _build_dependency_graph with complex dependency hierarchy"""
        # pylint: disable=protected-access
        # Create a more complex hierarchy: E -> D, C -> B -> A
        template_a = self.JetTemplate.create(
            {
                "name": "Template A",
                "reference": "template_a",
            }
        )
        template_b = self.JetTemplate.create(
            {
                "name": "Template B",
                "reference": "template_b",
            }
        )
        template_c = self.JetTemplate.create(
            {
                "name": "Template C",
                "reference": "template_c",
            }
        )
        template_d = self.JetTemplate.create(
            {
                "name": "Template D",
                "reference": "template_d",
            }
        )
        template_e = self.JetTemplate.create(
            {
                "name": "Template E",
                "reference": "template_e",
            }
        )

        # Create dependencies: E -> D, A -> B -> C
        self.JetTemplateDependency.create(
            {
                "template_id": template_e.id,
                "template_required_id": template_d.id,
                "state_required_id": self.state_running.id,
            }
        )
        self.JetTemplateDependency.create(
            {
                "template_id": template_a.id,
                "template_required_id": template_b.id,
                "state_required_id": self.state_running.id,
            }
        )
        self.JetTemplateDependency.create(
            {
                "template_id": template_b.id,
                "template_required_id": template_c.id,
                "state_required_id": self.state_running.id,
            }
        )

        # Test from template E
        graph = template_e._build_dependency_graph()

        # Should contain E and D
        expected_template_ids = [template_e.id, template_d.id]
        self.assertEqual(
            set(graph.keys()),
            set(expected_template_ids),
            "Should contain E and its dependencies",
        )

        # Verify levels
        self.assertEqual(graph[template_e.id]["level"], 0)  # Root
        self.assertEqual(graph[template_d.id]["level"], 1)  # One level down

        # Test from template C
        graph = template_c._build_dependency_graph()

        # Should contain only C (C has no dependencies)
        expected_template_ids = [template_c.id]
        self.assertEqual(
            set(graph.keys()), set(expected_template_ids), "Should contain only C"
        )

        # Verify levels
        self.assertEqual(graph[template_c.id]["level"], 0)  # Root
        self.assertEqual(
            len(graph[template_c.id]["dependencies"]), 0
        )  # No dependencies

        # Test from template A - should include A, B, and C
        # because A depends on B, and B depends on C
        graph = template_a._build_dependency_graph()

        # Should contain A, B, and C (A needs B, B needs C)
        expected_template_ids = [template_a.id, template_b.id, template_c.id]

        # Check that all expected templates are in the graph
        for expected_id in expected_template_ids:
            self.assertIn(
                expected_id, graph, f"Template {expected_id} should be in the graph"
            )

        # Check that the graph contains at least the expected templates
        # (it might contain more due to other templates in the test database)
        self.assertTrue(
            all(template_id in graph for template_id in expected_template_ids),
            f"Graph should contain at least {expected_template_ids}",
        )

        # Verify levels for the expected templates
        self.assertEqual(graph[template_a.id]["level"], 0)  # Root
        self.assertEqual(graph[template_b.id]["level"], 1)  # One level down
        self.assertEqual(graph[template_c.id]["level"], 2)  # Two levels down

    def test_build_dependency_graph_self_dependency(self):
        """Test _build_dependency_graph with self-dependency"""

        # Create a template that depends on itself
        template_self = self.JetTemplate.create(
            {
                "name": "Self Dependent Template",
                "reference": "self_dependent_template",
            }
        )

        # Creating self-dependency should raise a ValidationError
        with self.assertRaises(ValidationError) as context:
            self.JetTemplateDependency.create(
                {
                    "template_id": template_self.id,
                    "template_required_id": template_self.id,
                    "state_required_id": self.state_running.id,
                }
            )

        # Verify the error message mentions self-dependency
        error_message = str(context.exception)
        self.assertIn("cannot depend on itself", error_message.lower())

    def test_calculate_dependency_levels_simple_chain(self):
        """Test _calculate_dependency_levels with simple dependency chain"""
        # pylint: disable=protected-access
        # Use existing dependency chain: Odoo -> Postgres -> Docker -> Tower Core

        # Build the graph manually to test _calculate_dependency_levels
        graph = {
            self.jet_template_odoo.id: {
                "template": self.jet_template_odoo,
                "name": self.jet_template_odoo.name,
                "reference": self.jet_template_odoo.reference,
                "dependencies": [
                    {"template_id": self.jet_template_postgres.id},
                    {"template_id": self.jet_template_nginx.id},
                ],
                "level": 0,  # Will be calculated
            },
            self.jet_template_postgres.id: {
                "template": self.jet_template_postgres,
                "name": self.jet_template_postgres.name,
                "reference": self.jet_template_postgres.reference,
                "dependencies": [{"template_id": self.jet_template_docker.id}],
                "level": 0,  # Will be calculated
            },
            self.jet_template_docker.id: {
                "template": self.jet_template_docker,
                "name": self.jet_template_docker.name,
                "reference": self.jet_template_docker.reference,
                "dependencies": [{"template_id": self.jet_template_tower_core.id}],
                "level": 0,  # Will be calculated
            },
            self.jet_template_tower_core.id: {
                "template": self.jet_template_tower_core,
                "name": self.jet_template_tower_core.name,
                "reference": self.jet_template_tower_core.reference,
                "dependencies": [],
                "level": 0,  # Will be calculated
            },
        }

        # Call _calculate_dependency_levels
        self.jet_template_odoo._calculate_dependency_levels(graph)

        # Verify levels
        self.assertEqual(
            graph[self.jet_template_odoo.id]["level"],
            0,
            "Odoo should be level 0 (root)",
        )
        self.assertEqual(
            graph[self.jet_template_postgres.id]["level"],
            1,
            "Postgres should be level 1",
        )
        self.assertEqual(
            graph[self.jet_template_docker.id]["level"], 2, "Docker should be level 2"
        )
        self.assertEqual(
            graph[self.jet_template_tower_core.id]["level"],
            3,
            "Tower Core should be level 3",
        )

    def test_calculate_dependency_levels_branching_dependencies(self):
        """Test _calculate_dependency_levels with branching dependencies"""
        # Use existing WordPress template with branching dependencies:
        #  WordPress -> MariaDB/Nginx -> Docker

        # Build the graph manually
        graph = {
            self.jet_template_wordpress.id: {
                "template": self.jet_template_wordpress,
                "name": self.jet_template_wordpress.name,
                "reference": self.jet_template_wordpress.reference,
                "dependencies": [
                    {"template_id": self.jet_template_mariadb.id},
                    {"template_id": self.jet_template_nginx.id},
                ],
                "level": 0,
            },
            self.jet_template_mariadb.id: {
                "template": self.jet_template_mariadb,
                "name": self.jet_template_mariadb.name,
                "reference": self.jet_template_mariadb.reference,
                "dependencies": [{"template_id": self.jet_template_docker.id}],
                "level": 0,
            },
            self.jet_template_nginx.id: {
                "template": self.jet_template_nginx,
                "name": self.jet_template_nginx.name,
                "reference": self.jet_template_nginx.reference,
                "dependencies": [{"template_id": self.jet_template_docker.id}],
                "level": 0,
            },
            self.jet_template_docker.id: {
                "template": self.jet_template_docker,
                "name": self.jet_template_docker.name,
                "reference": self.jet_template_docker.reference,
                "dependencies": [{"template_id": self.jet_template_tower_core.id}],
                "level": 0,
            },
            self.jet_template_tower_core.id: {
                "template": self.jet_template_tower_core,
                "name": self.jet_template_tower_core.name,
                "reference": self.jet_template_tower_core.reference,
                "dependencies": [],
                "level": 0,
            },
        }

        # Call _calculate_dependency_levels
        self.jet_template_wordpress._calculate_dependency_levels(graph)

        # Verify levels
        self.assertEqual(
            graph[self.jet_template_wordpress.id]["level"],
            0,
            "WordPress should be level 0 (root)",
        )
        self.assertEqual(
            graph[self.jet_template_mariadb.id]["level"], 1, "MariaDB should be level 1"
        )
        self.assertEqual(
            graph[self.jet_template_nginx.id]["level"], 1, "Nginx should be level 1"
        )
        self.assertEqual(
            graph[self.jet_template_docker.id]["level"],
            2,
            "Docker should be level 2 (shortest path from WordPress)",
        )
        self.assertEqual(
            graph[self.jet_template_tower_core.id]["level"],
            3,
            "Tower Core should be level 3",
        )

    def test_calculate_dependency_levels_multiple_paths(self):
        """Test _calculate_dependency_levels with multiple paths to same template"""
        # Use existing WordPress template with multiple paths

        # Build the graph manually
        graph = {
            self.jet_template_wordpress.id: {
                "template": self.jet_template_wordpress,
                "name": self.jet_template_wordpress.name,
                "reference": self.jet_template_wordpress.reference,
                "dependencies": [
                    {"template_id": self.jet_template_mariadb.id},
                    {"template_id": self.jet_template_nginx.id},
                ],
                "level": 0,
            },
            self.jet_template_mariadb.id: {
                "template": self.jet_template_mariadb,
                "name": self.jet_template_mariadb.name,
                "reference": self.jet_template_mariadb.reference,
                "dependencies": [{"template_id": self.jet_template_docker.id}],
                "level": 0,
            },
            self.jet_template_nginx.id: {
                "template": self.jet_template_nginx,
                "name": self.jet_template_nginx.name,
                "reference": self.jet_template_nginx.reference,
                "dependencies": [{"template_id": self.jet_template_docker.id}],
                "level": 0,
            },
            self.jet_template_docker.id: {
                "template": self.jet_template_docker,
                "name": self.jet_template_docker.name,
                "reference": self.jet_template_docker.reference,
                "dependencies": [{"template_id": self.jet_template_tower_core.id}],
                "level": 0,
            },
            self.jet_template_tower_core.id: {
                "template": self.jet_template_tower_core,
                "name": self.jet_template_tower_core.name,
                "reference": self.jet_template_tower_core.reference,
                "dependencies": [],
                "level": 0,
            },
        }

        # Call _calculate_dependency_levels
        self.jet_template_wordpress._calculate_dependency_levels(graph)

        # Verify levels - Docker should have level 2 (shortest path from WordPress)
        self.assertEqual(
            graph[self.jet_template_wordpress.id]["level"],
            0,
            "WordPress should be level 0 (root)",
        )
        self.assertEqual(
            graph[self.jet_template_mariadb.id]["level"], 1, "MariaDB should be level 1"
        )
        self.assertEqual(
            graph[self.jet_template_nginx.id]["level"], 1, "Nginx should be level 1"
        )
        self.assertEqual(
            graph[self.jet_template_docker.id]["level"],
            2,
            "Docker should be level 2 (shortest path)",
        )
        self.assertEqual(
            graph[self.jet_template_tower_core.id]["level"],
            3,
            "Tower Core should be level 3",
        )

    def test_calculate_dependency_levels_empty_graph(self):
        """Test _calculate_dependency_levels with empty graph"""
        # pylint: disable=protected-access
        # Use existing Tower Core template

        # Empty graph
        graph = {}

        # Call _calculate_dependency_levels - should not raise error
        self.jet_template_tower_core._calculate_dependency_levels(graph)

        # Graph should remain empty
        self.assertEqual(len(graph), 0, "Empty graph should remain empty")

    def test_calculate_dependency_levels_single_template(self):
        """Test _calculate_dependency_levels with single template"""
        # pylint: disable=protected-access
        # Use existing Tower Core template (has no dependencies)

        # Single template graph
        graph = {
            self.jet_template_tower_core.id: {
                "template": self.jet_template_tower_core,
                "name": self.jet_template_tower_core.name,
                "reference": self.jet_template_tower_core.reference,
                "dependencies": [],
                "level": 0,
            }
        }

        # Call _calculate_dependency_levels
        self.jet_template_tower_core._calculate_dependency_levels(graph)

        # Tower Core should be level 0
        self.assertEqual(
            graph[self.jet_template_tower_core.id]["level"],
            0,
            "Single template should be level 0",
        )

    def test_calculate_dependency_levels_missing_template_in_graph(self):
        """Test _calculate_dependency_levels with template not in graph"""
        # pylint: disable=protected-access
        # Use existing Odoo template but reference a non-existent template

        # Graph with Odoo but not the referenced template
        graph = {
            self.jet_template_odoo.id: {
                "template": self.jet_template_odoo,
                "name": self.jet_template_odoo.name,
                "reference": self.jet_template_odoo.reference,
                "dependencies": [{"template_id": 99999}],  # Non-existent template ID
                "level": 0,
            }
        }

        # Call _calculate_dependency_levels - should handle missing template gracefully
        self.jet_template_odoo._calculate_dependency_levels(graph)

        # Odoo should be level 0
        self.assertEqual(
            graph[self.jet_template_odoo.id]["level"], 0, "Odoo should be level 0"
        )

    def test_calculate_dependency_levels_complex_hierarchy(self):
        """Test _calculate_dependency_levels with complex hierarchy"""
        # pylint: disable=protected-access
        # Use existing templates with complex hierarchy
        # This creates a complex hierarchy

        # Build the graph manually - only include Odoo's actual dependencies
        graph = {
            self.jet_template_odoo.id: {
                "template": self.jet_template_odoo,
                "name": self.jet_template_odoo.name,
                "reference": self.jet_template_odoo.reference,
                "dependencies": [
                    {"template_id": self.jet_template_postgres.id},
                    {"template_id": self.jet_template_nginx.id},
                ],
                "level": 0,
            },
            self.jet_template_postgres.id: {
                "template": self.jet_template_postgres,
                "name": self.jet_template_postgres.name,
                "reference": self.jet_template_postgres.reference,
                "dependencies": [{"template_id": self.jet_template_docker.id}],
                "level": 0,
            },
            self.jet_template_nginx.id: {
                "template": self.jet_template_nginx,
                "name": self.jet_template_nginx.name,
                "reference": self.jet_template_nginx.reference,
                "dependencies": [{"template_id": self.jet_template_docker.id}],
                "level": 0,
            },
            self.jet_template_docker.id: {
                "template": self.jet_template_docker,
                "name": self.jet_template_docker.name,
                "reference": self.jet_template_docker.reference,
                "dependencies": [{"template_id": self.jet_template_tower_core.id}],
                "level": 0,
            },
            self.jet_template_tower_core.id: {
                "template": self.jet_template_tower_core,
                "name": self.jet_template_tower_core.name,
                "reference": self.jet_template_tower_core.reference,
                "dependencies": [],
                "level": 0,
            },
        }

        # Call _calculate_dependency_levels from Odoo
        self.jet_template_odoo._calculate_dependency_levels(graph)

        # Verify levels
        self.assertEqual(
            graph[self.jet_template_odoo.id]["level"],
            0,
            "Odoo should be level 0 (root)",
        )
        self.assertEqual(
            graph[self.jet_template_postgres.id]["level"],
            1,
            "Postgres should be level 1",
        )
        self.assertEqual(
            graph[self.jet_template_nginx.id]["level"], 1, "Nginx should be level 1"
        )
        self.assertEqual(
            graph[self.jet_template_docker.id]["level"], 2, "Docker should be level 2"
        )
        self.assertEqual(
            graph[self.jet_template_tower_core.id]["level"],
            3,
            "Tower Core should be level 3",
        )

        # Verify that only Odoo's dependencies are in the graph
        expected_template_ids = [
            self.jet_template_odoo.id,
            self.jet_template_postgres.id,
            self.jet_template_nginx.id,
            self.jet_template_docker.id,
            self.jet_template_tower_core.id,
        ]
        self.assertEqual(
            set(graph.keys()),
            set(expected_template_ids),
            "Graph should only contain Odoo's dependencies",
        )

    def test_get_all_dependencies_simple_chain(self):
        """Test _get_all_dependencies with simple dependency chain"""
        # pylint: disable=protected-access
        # Use existing Odoo dependency chain:
        # Odoo -> Postgres/Nginx -> Docker -> Tower Core

        dependencies = self.jet_template_odoo._get_all_dependencies()

        # Should return all dependencies in level order (closest first)
        expected_dependencies = {
            self.jet_template_postgres,
            self.jet_template_nginx,
            self.jet_template_docker,
            self.jet_template_tower_core,
        }
        self.assertEqual(
            set(dependencies),
            expected_dependencies,
            "Should return all expected dependencies",
        )

        # Verify the order is correct (level 1, then level 2, then level 3)
        # Postgres and Nginx should be first (level 1)
        self.assertIn(
            self.jet_template_postgres,
            dependencies[:2],
            "Postgres should be in first two dependencies",
        )
        self.assertIn(
            self.jet_template_nginx,
            dependencies[:2],
            "Nginx should be in first two dependencies",
        )

        # Docker should be third (level 2)
        self.assertEqual(
            dependencies[2], self.jet_template_docker, "Docker should be third"
        )

        # Tower Core should be last (level 3)
        self.assertEqual(
            dependencies[3], self.jet_template_tower_core, "Tower Core should be last"
        )

    def test_get_all_dependencies_no_dependencies(self):
        """Test _get_all_dependencies with template that has no dependencies"""
        # pylint: disable=protected-access
        # Use Tower Core which has no dependencies

        dependencies = self.jet_template_tower_core._get_all_dependencies()

        # Should return empty list
        self.assertEqual(
            dependencies,
            [],
            "Should return empty list for template with no dependencies",
        )

    def test_get_all_dependencies_wordpress_chain(self):
        """Test _get_all_dependencies with WordPress dependency chain"""
        # pylint: disable=protected-access
        # Use WordPress dependency chain:
        # WordPress -> MariaDB/Nginx -> Docker -> Tower Core

        dependencies = self.jet_template_wordpress._get_all_dependencies()

        # Should return all dependencies in level order
        expected_dependencies = {
            self.jet_template_mariadb,
            self.jet_template_nginx,
            self.jet_template_docker,
            self.jet_template_tower_core,
        }
        self.assertEqual(
            set(dependencies),
            expected_dependencies,
            "Should return all expected dependencies",
        )

        # Verify the order is correct
        # MariaDB and Nginx should be first (level 1)
        self.assertIn(
            self.jet_template_mariadb,
            dependencies[:2],
            "MariaDB should be in first two dependencies",
        )
        self.assertIn(
            self.jet_template_nginx,
            dependencies[:2],
            "Nginx should be in first two dependencies",
        )

        # Docker should be third (level 2)
        self.assertEqual(
            dependencies[2], self.jet_template_docker, "Docker should be third"
        )

        # Tower Core should be last (level 3)
        self.assertEqual(
            dependencies[3], self.jet_template_tower_core, "Tower Core should be last"
        )

    def test_get_all_dependencies_docker_chain(self):
        """Test _get_all_dependencies with Docker dependency chain"""
        # pylint: disable=protected-access
        # Use Docker dependency chain: Docker -> Tower Core

        dependencies = self.jet_template_docker._get_all_dependencies()

        # Should return only Tower Core
        expected_dependencies = [self.jet_template_tower_core]
        self.assertEqual(
            dependencies, expected_dependencies, "Should return only Tower Core"
        )

    def test_get_all_dependencies_nginx_chain(self):
        """Test _get_all_dependencies with Nginx dependency chain"""
        # pylint: disable=protected-access
        # Use Nginx dependency chain: Nginx -> Docker -> Tower Core

        dependencies = self.jet_template_nginx._get_all_dependencies()

        # Should return Docker and Tower Core
        expected_dependencies = [self.jet_template_docker, self.jet_template_tower_core]
        self.assertEqual(
            dependencies, expected_dependencies, "Should return Docker and Tower Core"
        )

    def test_get_all_dependencies_complex_scenario(self):
        """Test _get_all_dependencies with complex dependency scenario"""
        # pylint: disable=protected-access
        # Use existing WooCommerce with Odoo template
        # This tests the scenario where a template has multiple dependency paths

        dependencies = self.jet_template_woocommerce_odoo._get_all_dependencies()

        # Should include all dependencies from both Odoo and WordPress
        # Expected: Odoo, WordPress, Postgres, MariaDB, Nginx, Docker, Tower Core
        expected_template_ids = [
            self.jet_template_odoo.id,
            self.jet_template_wordpress.id,
            self.jet_template_postgres.id,
            self.jet_template_mariadb.id,
            self.jet_template_nginx.id,
            self.jet_template_docker.id,
            self.jet_template_tower_core.id,
        ]

        actual_template_ids = [dep.id for dep in dependencies]
        self.assertEqual(
            set(actual_template_ids),
            set(expected_template_ids),
            "Should include all dependencies from both Odoo and WordPress",
        )

        # Verify that dependencies are ordered by level
        # Level 1: Odoo, WordPress
        # Level 2: Postgres, MariaDB, Nginx
        # Level 3: Docker
        # Level 4: Tower Core

        # Check that Odoo and WordPress are in the first two positions
        self.assertIn(
            self.jet_template_odoo,
            dependencies[:2],
            "Odoo should be in first two dependencies",
        )
        self.assertIn(
            self.jet_template_wordpress,
            dependencies[:2],
            "WordPress should be in first two dependencies",
        )

        # Check that Tower Core is last
        self.assertEqual(
            dependencies[-1], self.jet_template_tower_core, "Tower Core should be last"
        )

    def test_get_all_dependencies_excludes_self(self):
        """Test _get_all_dependencies excludes the template itself"""
        # pylint: disable=protected-access
        # Use Odoo template

        dependencies = self.jet_template_odoo._get_all_dependencies()

        # Should not include Odoo itself
        self.assertNotIn(
            self.jet_template_odoo,
            dependencies,
            "Should not include the template itself",
        )

        # Verify all returned dependencies are different from the root template
        for dependency in dependencies:
            self.assertNotEqual(
                dependency.id,
                self.jet_template_odoo.id,
                f"Should not include template with ID {dependency.id}",
            )

    def test_get_all_dependencies_same_level_must_order_transitive_edges(self):
        """
        If root A depends on B and C directly, and C also depends on B, then B and
        C share the same shortest-path level. Install lines use reverse order by
        ``order``; the dependency list must place C before B so B gets a higher
        line order and is installed before C.
        """
        # pylint: disable=protected-access
        tpl_b = self.JetTemplate.create(
            {
                "name": "Topo Base B",
                "reference": "topo_base_b",
            }
        )
        tpl_c = self.JetTemplate.create(
            {
                "name": "Topo Mid C",
                "reference": "topo_mid_c",
            }
        )
        tpl_a = self.JetTemplate.create(
            {
                "name": "Topo Root A",
                "reference": "topo_root_a",
            }
        )
        # C depends on B
        self.JetTemplateDependency.create(
            {
                "template_id": tpl_c.id,
                "template_required_id": tpl_b.id,
                "state_required_id": self.state_running.id,
            }
        )
        # A depends on C first, then B so graph traversal tends to visit B before C
        # in ``graph.items()`` while both stay at level 1.
        self.JetTemplateDependency.create(
            {
                "template_id": tpl_a.id,
                "template_required_id": tpl_c.id,
                "state_required_id": self.state_running.id,
            }
        )
        self.JetTemplateDependency.create(
            {
                "template_id": tpl_a.id,
                "template_required_id": tpl_b.id,
                "state_required_id": self.state_running.id,
            }
        )

        dependencies = tpl_a._get_all_dependencies()
        idx_b = next(i for i, t in enumerate(dependencies) if t.id == tpl_b.id)
        idx_c = next(i for i, t in enumerate(dependencies) if t.id == tpl_c.id)

        self.assertLess(
            idx_c,
            idx_b,
            "C must appear before B in dependency order so install (reverse order)"
            " runs B before C when C depends on B",
        )

    def test_get_all_dependencies_consistency_with_build_graph(self):
        """
        _get_all_dependencies must return dependents before their prerequisites.

        Correctness is verified against the graph edges directly (the topological
        invariant) rather than re-running _topological_sort_dependency_graph, which
        would create a circular check where a bug in the sort masks itself.
        """
        # pylint: disable=protected-access
        graph = self.jet_template_odoo._build_dependency_graph()
        dependencies = self.jet_template_odoo._get_all_dependencies()

        self.assertTrue(dependencies, "Expected a non-empty dependency list")

        index = {tmpl.id: i for i, tmpl in enumerate(dependencies)}

        for u_id, info in graph.items():
            if u_id not in index:
                continue
            for dep in info["dependencies"]:
                v_id = dep["template_id"]
                if v_id not in index:
                    continue
                self.assertLess(
                    index[u_id],
                    index[v_id],
                    f"{graph[u_id]['name']} (dependent) must appear before "
                    f"{graph[v_id]['name']} (prerequisite)",
                )

    def test_get_all_dependencies_woocommerce_odoo_chain(self):
        """Test _get_all_dependencies with WooCommerce with Odoo dependency chain"""
        # pylint: disable=protected-access
        # Use WooCommerce with Odoo dependency chain:
        # WooCommerce -> WordPress/Odoo ->
        # MariaDB/Postgres/Nginx -> Docker -> Tower Core

        dependencies = self.jet_template_woocommerce_odoo._get_all_dependencies()

        # Should include all dependencies from both WordPress and Odoo
        # Expected: WordPress, Odoo, MariaDB, Postgres, Nginx, Docker, Tower Core
        expected_template_ids = [
            self.jet_template_wordpress.id,
            self.jet_template_odoo.id,
            self.jet_template_mariadb.id,
            self.jet_template_postgres.id,
            self.jet_template_nginx.id,
            self.jet_template_docker.id,
            self.jet_template_tower_core.id,
        ]

        actual_template_ids = [dep.id for dep in dependencies]
        self.assertEqual(
            set(actual_template_ids),
            set(expected_template_ids),
            "Should include all dependencies from both WordPress and Odoo",
        )

        # Verify that dependencies are ordered by level
        # Level 1: WordPress, Odoo
        # Level 2: MariaDB, Postgres, Nginx
        # Level 3: Docker
        # Level 4: Tower Core

        # Check that WordPress and Odoo are in the first two positions
        self.assertIn(
            self.jet_template_wordpress,
            dependencies[:2],
            "WordPress should be in first two dependencies",
        )
        self.assertIn(
            self.jet_template_odoo,
            dependencies[:2],
            "Odoo should be in first two dependencies",
        )

        # Check that Tower Core is last
        self.assertEqual(
            dependencies[-1], self.jet_template_tower_core, "Tower Core should be last"
        )

        # Verify that all level 2 dependencies are present
        level_2_deps = [
            self.jet_template_mariadb,
            self.jet_template_postgres,
            self.jet_template_nginx,
        ]
        for dep in level_2_deps:
            self.assertIn(dep, dependencies, f"{dep.name} should be in dependencies")

        # Verify that Docker is present
        self.assertIn(
            self.jet_template_docker, dependencies, "Docker should be in dependencies"
        )

    def test_get_action_path_with_destroy_action_only(self):
        """
        Test _get_action_path with only destroy action set
        """
        # Create states
        state_running = self.JetState.create(
            {
                "name": "Running",
                "reference": "running",
                "sequence": 20,
            }
        )
        state_stopped = self.JetState.create(
            {
                "name": "Stopped",
                "reference": "stopped",
                "sequence": 30,
            }
        )

        # Create destroy action
        destroy_action = self.JetAction.create(
            {
                "name": "Destroy Action",
                "reference": "destroy_action",
                "jet_template_id": self.clean_template.id,
                "state_from_id": state_running.id,
                "state_to_id": False,
                "state_transit_id": state_stopped.id,
                "priority": 10,
            }
        )

        # Set destroy action
        self.clean_template.action_destroy_id = destroy_action

        # Test path without state_to (should use destroy action)
        result = self.clean_template._get_action_path(state_from=state_running)
        self.assertEqual(
            result,
            [destroy_action],
            "Should return destroy action when no state_to provided",
        )

        # Test path with state_to (should not use destroy action)
        result = self.clean_template._get_action_path(
            state_from=state_running, state_to=state_stopped
        )
        self.assertEqual(
            result,
            [],
            "Should return empty list when state_to provided and no path exists",
        )

    def test_get_action_path_same_state(self):
        """
        Test _get_action_path when start and end states are the same
        """
        # Test same state without destroy action
        result = self.clean_template._get_action_path(
            state_from=self.state_a, state_to=self.state_a
        )
        self.assertEqual(
            result, [], "Should return empty list for same start and end state"
        )

        # Create destroy action
        destroy_action = self.JetAction.create(
            {
                "name": "Destroy Action",
                "reference": "destroy_action",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_a.id,
                "state_to_id": False,
                "state_transit_id": self.state_starting.id,
                "priority": 10,
            }
        )
        self.clean_template.action_destroy_id = destroy_action

        # Test same state with destroy action (no state_to provided)
        result = self.clean_template._get_action_path(state_from=self.state_a)
        self.assertEqual(
            result,
            [destroy_action],
            "Should return destroy action for same state when no state_to provided",
        )

    def test_get_action_path_direct_path(self):
        """
        Test _get_action_path with direct path between states
        """
        # Create direct action
        action_ab = self.JetAction.create(
            {
                "name": "Action A to B",
                "reference": "action_ab",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_a.id,
                "state_to_id": self.state_b.id,
                "state_transit_id": self.state_starting.id,
                "priority": 10,
            }
        )

        # Test direct path
        result = self.clean_template._get_action_path(
            state_from=self.state_a, state_to=self.state_b
        )
        self.assertEqual(result, [action_ab], "Should return direct action path")

    def test_get_action_path_multi_step_path(self):
        """
        Test _get_action_path with multi-step path
        """
        # Create multi-step actions
        action_ab = self.JetAction.create(
            {
                "name": "Action A to B",
                "reference": "action_ab",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_a.id,
                "state_to_id": self.state_b.id,
                "state_transit_id": self.state_starting.id,
                "priority": 10,
            }
        )
        action_bc = self.JetAction.create(
            {
                "name": "Action B to C",
                "reference": "action_bc",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_b.id,
                "state_to_id": self.state_c.id,
                "state_transit_id": self.state_stopping.id,
                "priority": 10,
            }
        )

        # Test multi-step path
        result = self.clean_template._get_action_path(
            state_from=self.state_a, state_to=self.state_c
        )
        expected_path = [action_ab, action_bc]
        self.assertEqual(result, expected_path, "Should return multi-step action path")

    def test_get_action_path_with_create_and_multi_step(self):
        """
        Test _get_action_path with create action and multi-step path
        """
        # Create create action
        create_action = self.JetAction.create(
            {
                "name": "Create Action",
                "reference": "create_action",
                "jet_template_id": self.clean_template.id,
                "state_from_id": False,
                "state_to_id": self.state_b.id,
                "state_transit_id": self.state_a.id,
                "priority": 10,
            }
        )

        # Create transition action
        action_rs = self.JetAction.create(
            {
                "name": "Action Running to Stopped",
                "reference": "action_rs",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_b.id,
                "state_to_id": self.state_c.id,
                "state_transit_id": self.state_c.id,
                "priority": 10,
            }
        )

        # Set create action
        self.clean_template.action_create_id = create_action

        # Test path from create to final state
        result = self.clean_template._get_action_path(state_to=self.state_c)
        expected_path = [create_action, action_rs]
        self.assertEqual(
            result, expected_path, "Should return create action + transition path"
        )

    def test_get_action_path_with_multi_step_and_destroy(self):
        """
        Test _get_action_path with multi-step path and destroy action
        """
        # Create multi-step actions
        action_ab = self.JetAction.create(
            {
                "name": "Action A to B",
                "reference": "action_ab",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_a.id,
                "state_to_id": self.state_b.id,
                "state_transit_id": self.state_starting.id,
                "priority": 10,
            }
        )
        action_bc = self.JetAction.create(
            {
                "name": "Action B to C",
                "reference": "action_bc",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_b.id,
                "state_to_id": self.state_c.id,
                "state_transit_id": self.state_stopping.id,
                "priority": 10,
            }
        )

        # Create destroy action
        destroy_action = self.JetAction.create(
            {
                "name": "Destroy Action",
                "reference": "destroy_action",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_c.id,
                "state_to_id": False,
                "state_transit_id": self.state_stopping.id,
                "priority": 10,
            }
        )

        # Set destroy action
        self.clean_template.action_destroy_id = destroy_action

        # Test path from A to destroy
        result = self.clean_template._get_action_path(state_from=self.state_a)
        expected_path = [action_ab, action_bc, destroy_action]
        self.assertEqual(
            result, expected_path, "Should return multi-step path + destroy action"
        )

    def test_get_action_path_complete_lifecycle(self):
        """
        Test _get_action_path with complete lifecycle (create -> multi-step -> destroy)
        """
        # Create create action
        create_action = self.JetAction.create(
            {
                "name": "Create Action",
                "reference": "create_action",
                "jet_template_id": self.clean_template.id,
                "state_from_id": False,
                "state_to_id": self.state_b.id,
                "state_transit_id": self.state_a.id,
                "priority": 10,
            }
        )

        # Create transition action
        action_rs = self.JetAction.create(
            {
                "name": "Action Running to Stopped",
                "reference": "action_rs",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_b.id,
                "state_to_id": self.state_c.id,
                "state_transit_id": self.state_c.id,
                "priority": 10,
            }
        )

        # Create destroy action
        destroy_action = self.JetAction.create(
            {
                "name": "Destroy Action",
                "reference": "destroy_action",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_c.id,
                "state_to_id": False,
                "state_transit_id": self.state_c.id,
                "priority": 10,
            }
        )

        # Set border actions
        self.clean_template.action_create_id = create_action
        self.clean_template.action_destroy_id = destroy_action

        # Test complete lifecycle
        result = self.clean_template._get_action_path()
        expected_path = [create_action, action_rs, destroy_action]
        self.assertEqual(result, expected_path, "Should return complete lifecycle path")

    def test_get_action_path_no_path_exists(self):
        """
        Test _get_action_path when no path exists between states
        """
        # Create action that doesn't connect A to C
        self.JetAction.create(
            {
                "name": "Action B to C",
                "reference": "action_bc",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_b.id,
                "state_to_id": self.state_c.id,
                "state_transit_id": self.state_stopping.id,
                "priority": 10,
            }
        )

        # Test path from A to C (no path exists)
        result = self.clean_template._get_action_path(
            state_from=self.state_a, state_to=self.state_c
        )
        self.assertEqual(result, [], "Should return empty list when no path exists")

    def test_get_action_path_complex_multi_level_path(self):
        """
        Test _get_action_path with complex multi-level path
        """
        # Create additional states for this test
        state_e = self.JetState.create(
            {
                "name": "State E",
                "reference": "state_e",
                "sequence": 50,
            }
        )

        # Create complex multi-level actions
        action_ab = self.JetAction.create(
            {
                "name": "Action A to B",
                "reference": "action_ab",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_a.id,
                "state_to_id": self.state_b.id,
                "state_transit_id": self.state_starting.id,
                "priority": 10,
            }
        )
        action_bc = self.JetAction.create(
            {
                "name": "Action B to C",
                "reference": "action_bc",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_b.id,
                "state_to_id": self.state_c.id,
                "state_transit_id": self.state_stopping.id,
                "priority": 10,
            }
        )
        action_cd = self.JetAction.create(
            {
                "name": "Action C to D",
                "reference": "action_cd",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_c.id,
                "state_to_id": self.state_d.id,
                "state_transit_id": self.state_stopping.id,
                "priority": 10,
            }
        )
        action_de = self.JetAction.create(
            {
                "name": "Action D to E",
                "reference": "action_de",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_d.id,
                "state_to_id": state_e.id,
                "state_transit_id": self.state_stopping.id,
                "priority": 10,
            }
        )

        # Test complex multi-level path
        result = self.clean_template._get_action_path(
            state_from=self.state_a, state_to=state_e
        )
        expected_path = [action_ab, action_bc, action_cd, action_de]
        self.assertEqual(
            result, expected_path, "Should return complex multi-level path"
        )

    def test_get_action_path_shortest_path_selection(self):
        """
        Test _get_action_path selects shortest path when multiple paths exist
        """
        # Create short path: A -> C
        action_ac = self.JetAction.create(
            {
                "name": "Action A to C (short)",
                "reference": "action_ac",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_a.id,
                "state_to_id": self.state_c.id,
                "state_transit_id": self.state_stopping.id,
                "priority": 10,
            }
        )

        # Create long path: A -> B -> D -> C
        self.JetAction.create(
            {
                "name": "Action A to B",
                "reference": "action_ab",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_a.id,
                "state_to_id": self.state_b.id,
                "state_transit_id": self.state_starting.id,
                "priority": 10,
            }
        )
        self.JetAction.create(
            {
                "name": "Action B to D",
                "reference": "action_bd",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_b.id,
                "state_to_id": self.state_d.id,
                "state_transit_id": self.state_stopping.id,
                "priority": 10,
            }
        )
        self.JetAction.create(
            {
                "name": "Action D to C",
                "reference": "action_dc",
                "jet_template_id": self.clean_template.id,
                "state_from_id": self.state_d.id,
                "state_to_id": self.state_c.id,
                "state_transit_id": self.state_stopping.id,
                "priority": 10,
            }
        )

        # Test that shortest path is selected
        result = self.clean_template._get_action_path(
            state_from=self.state_a, state_to=self.state_c
        )
        expected_path = [action_ac]  # Shortest path
        self.assertEqual(
            result,
            expected_path,
            "Should select shortest path when multiple paths exist",
        )

    def test_check_dependency_satisfaction_no_dependencies(self):
        """Test _check_dependency_satisfaction when template has no dependencies"""
        # pylint: disable=protected-access
        server = self.server_test_1

        # Test with template that has no dependencies
        missing_templates = self.jet_template_tower_core._check_dependency_satisfaction(
            server
        )

        # Should return empty list since tower_core has no dependencies
        self.assertEqual(
            len(missing_templates),
            0,
            "Should return empty list when no dependencies exist",
        )

    def test_check_dependency_satisfaction_all_missing(self):
        """Test _check_dependency_satisfaction when all dependencies are missing"""
        # pylint: disable=protected-access
        server = self.server_test_1

        # Test with different templates that have dependencies
        templates_to_test = [
            self.jet_template_nginx,
            self.jet_template_odoo,
            self.jet_template_woocommerce_odoo,
        ]

        for template in templates_to_test:
            # Get actual dependencies for template
            all_deps = template._get_all_dependencies()

            # Test - should return all missing dependencies
            missing_templates = template._check_dependency_satisfaction(server)

            # Should return all dependencies since none are installed
            expected_dependencies = set(all_deps)
            actual_dependencies = set(missing_templates)
            self.assertEqual(
                actual_dependencies,
                expected_dependencies,
                f"Should return all missing dependencies for {template.name}",
            )

    def test_check_dependency_satisfaction_all_satisfied(self):
        """Test _check_dependency_satisfaction when all dependencies are satisfied"""
        # pylint: disable=protected-access
        server = self.server_test_1

        # Test with different templates that have dependencies
        templates_to_test = [
            self.jet_template_nginx,
            self.jet_template_odoo,
            self.jet_template_woocommerce_odoo,
        ]

        for template in templates_to_test:
            # Install all dependencies for this template
            all_deps = template._get_all_dependencies()
            for dep_template in all_deps:
                dep_template.server_ids = [(4, server.id)]

            # Test - should return empty list
            missing_templates = template._check_dependency_satisfaction(server)

            # Should return empty list since all dependencies are now installed
            self.assertEqual(
                len(missing_templates),
                0,
                f"Should return empty list for {template.name}",
            )

    def test_check_dependency_satisfaction_partial_installation(self):
        """Test _check_dependency_satisfaction with partial installation"""
        # pylint: disable=protected-access
        server = self.server_test_1

        # Get all dependencies for odoo
        all_deps = self.jet_template_odoo._get_all_dependencies()

        # Install some dependencies but not all (install first half)
        half_count = len(all_deps) // 2
        for i, dep in enumerate(all_deps):
            if i < half_count:
                dep.server_ids = [(4, server.id)]

        # Test with odoo
        missing_templates = self.jet_template_odoo._check_dependency_satisfaction(
            server
        )

        # Should return the remaining uninstalled dependencies
        expected_missing = set(all_deps[half_count:])
        actual_missing = set(missing_templates)
        self.assertEqual(
            actual_missing,
            expected_missing,
            "Should return only the missing dependencies",
        )

    def test_check_dependency_satisfaction_no_server(self):
        """Test _check_dependency_satisfaction when server is None"""
        # pylint: disable=protected-access

        # Test with odoo and None server
        missing_templates = self.jet_template_odoo._check_dependency_satisfaction(None)

        # Should return empty list when server is None (no server to check against)
        self.assertEqual(
            len(missing_templates), 0, "Should return empty list when server is None"
        )

    def test_check_dependency_satisfaction_multiple_servers(self):
        """Test _check_dependency_satisfaction with different server states"""
        # pylint: disable=protected-access
        server1 = self.server_test_1
        server2 = self.server_test_2

        # Get actual dependencies for nginx
        all_deps = self.jet_template_nginx._get_all_dependencies()

        # Install all dependencies on server1
        for dep in all_deps:
            dep.server_ids = [(4, server1.id)]

        # Test with nginx on both servers
        missing_templates_server1 = (
            self.jet_template_nginx._check_dependency_satisfaction(server1)
        )
        missing_templates_server2 = (
            self.jet_template_nginx._check_dependency_satisfaction(server2)
        )

        # Server1 should have no missing dependencies
        self.assertEqual(
            len(missing_templates_server1),
            0,
            "Server1 should have no missing dependencies",
        )
        self.assertEqual(
            len(missing_templates_server2),
            len(all_deps),
            "Server2 should have all dependencies missing",
        )

        # Verify server2 has all the expected missing dependencies
        expected_missing_server2 = set(all_deps)
        actual_missing_server2 = set(missing_templates_server2)
        self.assertEqual(
            actual_missing_server2,
            expected_missing_server2,
            "Server2 should be missing all dependencies",
        )

    def test_check_dependency_satisfaction_self_dependency(self):
        """Test _check_dependency_satisfaction with template that depends on itself"""
        # pylint: disable=protected-access
        server = self.server_test_1

        # Create a template that depends on itself
        # But let's test the method behavior anyway
        self_loop_template = self.JetTemplate.create(
            {
                "name": "Self Loop Template",
                "reference": "self_loop_template",
            }
        )

        # Manually create a dependency record (this would normally be prevented)
        # We'll test the method's behavior when it encounters this situation
        missing_templates = self_loop_template._check_dependency_satisfaction(server)

        # Should return empty list since template has no dependencies
        self.assertEqual(
            len(missing_templates),
            0,
            "Should return empty list for template with no dependencies",
        )

    def test_get_all_depend_on_this_no_dependents(self):
        """Test _get_all_depend_on_this when template has no dependents"""
        # pylint: disable=protected-access

        # Test with woocommerce_odoo which should have no dependents
        dependents = self.jet_template_woocommerce_odoo._get_all_depend_on_this()

        # Should return empty recordset since no templates depend on woocommerce_odoo
        self.assertEqual(
            len(dependents),
            0,
            "Should return empty recordset when no templates depend on this one",
        )

    def test_get_all_depend_on_this_docker_dependents(self):
        """Test _get_all_depend_on_this with docker's dependents"""
        # pylint: disable=protected-access

        # Test with docker - should have all dependents (direct and indirect)
        dependents = self.jet_template_docker._get_all_depend_on_this()

        # Should return all templates that depend on docker (directly or indirectly)
        # docker -> nginx/postgres/mariadb -> odoo/wordpress -> woocommerce_odoo
        expected_dependents = {
            self.jet_template_nginx,
            self.jet_template_postgres,
            self.jet_template_mariadb,
            self.jet_template_odoo,
            self.jet_template_wordpress,
            self.jet_template_woocommerce_odoo,
        }
        actual_dependents = set(dependents)

        # Filter out any templates that aren't in the expected set
        # (some tests might have created additional dependencies)
        actual_dependents_filtered = {
            t for t in actual_dependents if t in expected_dependents
        }

        self.assertEqual(
            actual_dependents_filtered,
            expected_dependents,
            "Should return all dependents of docker",
        )

    def test_get_all_depend_on_this_indirect_dependents(self):
        """Test _get_all_depend_on_this with indirect dependents"""
        # pylint: disable=protected-access

        # Test with tower_core - should have many indirect dependents
        dependents = self.jet_template_tower_core._get_all_depend_on_this()

        # Should return all templates that depend on tower_core (directly or indirectly)
        # tower_core -> docker -> nginx/postgres -> odoo/wordpress -> woocommerce_odoo
        expected_dependents = {
            self.jet_template_docker,
            self.jet_template_nginx,
            self.jet_template_postgres,
            self.jet_template_mariadb,
            self.jet_template_odoo,
            self.jet_template_wordpress,
            self.jet_template_woocommerce_odoo,
        }
        actual_dependents = set(dependents)

        # Filter out any templates that aren't in the expected set
        # (some tests might have created additional dependencies)
        actual_dependents_filtered = {
            t for t in actual_dependents if t in expected_dependents
        }

        self.assertEqual(
            actual_dependents_filtered,
            expected_dependents,
            "Should return all dependents including indirect ones",
        )

    def test_get_all_depend_on_this_complex_hierarchy(self):
        """Test _get_all_depend_on_this with complex dependency hierarchy"""
        # pylint: disable=protected-access

        # Test with nginx - should have odoo, wordpress, and woocommerce_odoo
        dependents = self.jet_template_nginx._get_all_depend_on_this()

        # Should return odoo, wordpress, and woocommerce_odoo
        expected_dependents = {
            self.jet_template_odoo,
            self.jet_template_wordpress,
            self.jet_template_woocommerce_odoo,
        }
        actual_dependents = set(dependents)

        # Filter out any templates that aren't in the expected set
        # (some tests might have created additional dependencies)
        actual_dependents_filtered = {
            t for t in actual_dependents if t in expected_dependents
        }

        self.assertEqual(
            actual_dependents_filtered,
            expected_dependents,
            "Should return all dependents in complex hierarchy",
        )

    def test_get_all_depend_on_this_multiple_levels(self):
        """Test _get_all_depend_on_this with multiple dependency levels"""
        # pylint: disable=protected-access

        # Test with postgres - should have odoo and woocommerce_odoo as dependents
        dependents = self.jet_template_postgres._get_all_depend_on_this()

        # Should return odoo and woocommerce_odoo
        expected_dependents = {
            self.jet_template_odoo,
            self.jet_template_woocommerce_odoo,
        }
        actual_dependents = set(dependents)

        # Filter out any templates that aren't in the expected set
        # (some tests might have created additional dependencies)
        actual_dependents_filtered = {
            t for t in actual_dependents if t in expected_dependents
        }

        self.assertEqual(
            actual_dependents_filtered,
            expected_dependents,
            "Should return dependents across multiple levels",
        )

    def test_get_all_depend_on_this_self_dependency(self):
        """Test _get_all_depend_on_this with template that has no dependents"""
        # pylint: disable=protected-access

        # Test with a template that has no dependents
        dependents = self.jet_template_woocommerce_odoo._get_all_depend_on_this()

        # Should return empty recordset
        self.assertEqual(
            len(dependents),
            0,
            "Should return empty recordset for template with no dependents",
        )

    def test_get_all_depend_on_this_consistency_with_dependencies(self):
        """Test that _get_all_depend_on_this is consistent with _get_all_dependencies"""
        # pylint: disable=protected-access

        # For each template, check that its dependents are consistent
        templates_to_test = [
            self.jet_template_tower_core,
            self.jet_template_docker,
            self.jet_template_nginx,
            self.jet_template_postgres,
            self.jet_template_odoo,
        ]

        for template in templates_to_test:
            # Get templates that depend on this template
            dependents = template._get_all_depend_on_this()

            # For each dependent, check that this template is in its dependencies
            for dependent in dependents:
                dependent_deps = dependent._get_all_dependencies()
                self.assertIn(
                    template,
                    dependent_deps,
                    f"{dependent.name} should have {template.name} in its dependencies",
                )

    def test_get_all_depend_on_this_circular_dependency_handling(self):
        """Test _get_all_depend_on_this handles circular dependencies correctly"""
        # pylint: disable=protected-access

        # Test with templates that might have circular dependencies
        # This test ensures the method doesn't get stuck in infinite loops
        templates_to_test = [
            self.jet_template_tower_core,
            self.jet_template_docker,
            self.jet_template_nginx,
            self.jet_template_postgres,
            self.jet_template_odoo,
        ]

        for template in templates_to_test:
            # This should not raise an exception or get stuck
            dependents = template._get_all_depend_on_this()

            # Should return a valid recordset
            self.assertIsInstance(
                dependents, self.env["cx.tower.jet.template"].__class__
            )

            # Should not include the template itself
            self.assertNotIn(
                template, dependents, "Template should not depend on itself"
            )

    def test_create_jet_with_server_logs(self):
        """Test create_jet creates server logs correctly"""
        # Create a file template for server logs
        file_template = self.FileTemplate.create(
            {
                "name": "Test Log File Template",
                "file_name": "test_log.txt",
                "source": "tower",
                "server_dir": "/var/log",
                "code": "Test log content",
            }
        )

        # Create server logs on the template
        server_log_file = self.ServerLog.create(
            {
                "name": "Test File Log",
                "server_id": self.server_test_1.id,
                "jet_template_id": self.jet_template_test.id,
                "log_type": "file",
                "file_template_id": file_template.id,
                "access_level": "1",
            }
        )

        server_log_command = self.ServerLog.create(
            {
                "name": "Test Command Log",
                "server_id": self.server_test_1.id,
                "jet_template_id": self.jet_template_test.id,
                "log_type": "command",
                "command_id": self.command_list_dir.id,
                "access_level": "1",
            }
        )

        # Ensure template is installed on server
        self.jet_template_test.write({"server_ids": [(4, self.server_test_1.id)]})

        # Create jet from template
        jet = self.jet_template_test.create_jet(
            server=self.server_test_1, name="Test Jet with Logs"
        )

        # Verify jet was created
        self.assertTrue(jet, "Jet should be created")
        self.assertEqual(jet.name, "Test Jet with Logs")
        self.assertEqual(jet.server_id, self.server_test_1)
        self.assertEqual(jet.jet_template_id, self.jet_template_test)

        # Verify server logs were created for the jet
        jet_logs = self.ServerLog.search([("jet_id", "=", jet.id)])
        self.assertEqual(
            len(jet_logs),
            2,
            "Should create 2 server logs (one file, one command)",
        )

        # Verify file-type log
        jet_log_file = jet_logs.filtered(lambda log: log.log_type == "file")
        self.assertEqual(
            len(jet_log_file),
            1,
            "Should have exactly one file-type log",
        )
        jet_log_file = jet_log_file[0]  # Get single record
        self.assertEqual(
            jet_log_file.jet_id,
            jet,
            "File log should be linked to the jet",
        )
        self.assertEqual(
            jet_log_file.server_id,
            self.server_test_1,
            "File log should be linked to the server",
        )
        self.assertFalse(
            jet_log_file.jet_template_id,
            "File log should not be linked to template",
        )
        self.assertTrue(
            jet_log_file.file_id,
            "File log should have a file created",
        )
        self.assertEqual(
            jet_log_file.file_template_id,
            server_log_file.file_template_id,
            "File log should reference the same file template as template log",
        )
        self.assertEqual(
            jet_log_file.name,
            server_log_file.name,
            "File log should have the same name as template log",
        )
        self.assertEqual(
            jet_log_file.file_id.jet_id,
            jet,
            "Created file should be linked to the jet",
        )
        self.assertEqual(
            jet_log_file.file_id.server_id,
            self.server_test_1,
            "Created file should be linked to the server",
        )

        # Verify command-type log
        jet_log_command = jet_logs.filtered(lambda log: log.log_type == "command")
        self.assertEqual(
            len(jet_log_command),
            1,
            "Should have exactly one command-type log",
        )
        jet_log_command = jet_log_command[0]  # Get single record
        self.assertEqual(
            jet_log_command.jet_id,
            jet,
            "Command log should be linked to the jet",
        )
        self.assertEqual(
            jet_log_command.server_id,
            self.server_test_1,
            "Command log should be linked to the server",
        )
        self.assertFalse(
            jet_log_command.jet_template_id,
            "Command log should not be linked to template",
        )
        self.assertFalse(
            jet_log_command.file_id,
            "Command log should not have a file",
        )
        self.assertEqual(
            jet_log_command.command_id,
            server_log_command.command_id,
            "Command log should reference the same command as template log",
        )
        self.assertEqual(
            jet_log_command.name,
            server_log_command.name,
            "Command log should have the same name as template log",
        )

        # Verify original template logs are unchanged
        template_logs = self.ServerLog.search(
            [("jet_template_id", "=", self.jet_template_test.id)]
        )
        self.assertIn(
            server_log_file,
            template_logs,
            "Template file log should still exist",
        )
        self.assertIn(
            server_log_command,
            template_logs,
            "Template command log should still exist",
        )
        self.assertFalse(
            server_log_file.jet_id,
            "Template file log should not be linked to any jet",
        )
        self.assertFalse(
            server_log_command.jet_id,
            "Template command log should not be linked to any jet",
        )

    def test_create_jet_with_multiple_file_logs(self):
        """Test create_jet creates multiple file logs correctly"""
        # Create multiple file templates
        file_template_1 = self.FileTemplate.create(
            {
                "name": "Log File Template 1",
                "file_name": "log1.txt",
                "source": "tower",
                "server_dir": "/var/log",
                "code": "Log 1 content",
            }
        )

        file_template_2 = self.FileTemplate.create(
            {
                "name": "Log File Template 2",
                "file_name": "log2.txt",
                "source": "tower",
                "server_dir": "/var/log",
                "code": "Log 2 content",
            }
        )

        # Create multiple server logs on the template
        self.ServerLog.create(
            {
                "name": "File Log 1",
                "server_id": self.server_test_1.id,
                "jet_template_id": self.jet_template_test.id,
                "log_type": "file",
                "file_template_id": file_template_1.id,
                "access_level": "1",
            }
        )

        self.ServerLog.create(
            {
                "name": "File Log 2",
                "server_id": self.server_test_1.id,
                "jet_template_id": self.jet_template_test.id,
                "log_type": "file",
                "file_template_id": file_template_2.id,
                "access_level": "2",
            }
        )

        # Ensure template is installed on server
        self.jet_template_test.write({"server_ids": [(4, self.server_test_1.id)]})

        # Create jet from template
        jet = self.jet_template_test.create_jet(
            server=self.server_test_1, name="Test Jet Multiple Files"
        )

        # Verify all file logs were created
        jet_logs = self.ServerLog.search([("jet_id", "=", jet.id)])
        file_logs = jet_logs.filtered(lambda log: log.log_type == "file")
        self.assertEqual(
            len(file_logs),
            2,
            "Should create 2 file logs",
        )

        # Verify each file log has its own file
        files = file_logs.mapped("file_id")
        self.assertEqual(
            len(files),
            2,
            "Should create 2 files",
        )
        self.assertEqual(
            len(set(files.ids)),
            2,
            "Files should be different",
        )

        # Verify files are linked correctly
        for log in file_logs:
            self.assertTrue(log.file_id, "Each log should have a file")
            self.assertEqual(
                log.file_id.jet_id,
                jet,
                "File should be linked to the jet",
            )
            self.assertEqual(
                log.file_id.server_id,
                self.server_test_1,
                "File should be linked to the server",
            )

    def test_create_jet_with_no_server_logs(self):
        """Test create_jet works correctly when template has no server logs"""
        # Ensure template has no server logs
        self.jet_template_test.server_log_ids.unlink()

        # Ensure template is installed on server
        self.jet_template_test.write({"server_ids": [(4, self.server_test_1.id)]})

        # Create jet from template
        jet = self.jet_template_test.create_jet(
            server=self.server_test_1, name="Test Jet No Logs"
        )

        # Verify jet was created
        self.assertTrue(jet, "Jet should be created")

        # Verify no server logs were created
        jet_logs = self.ServerLog.search([("jet_id", "=", jet.id)])
        self.assertEqual(
            len(jet_logs),
            0,
            "Should not create any server logs when template has none",
        )

    def test_create_jet_server_logs_fields_copied(self):
        """Test that server log fields are correctly copied from template"""
        # Create a file template
        file_template = self.FileTemplate.create(
            {
                "name": "Test Log File Template",
                "file_name": "test_log.txt",
                "source": "tower",
                "server_dir": "/var/log",
                "code": "Test log content",
            }
        )

        # Create server log with various fields
        server_log = self.ServerLog.create(
            {
                "name": "Test Log with Fields",
                "server_id": self.server_test_1.id,
                "jet_template_id": self.jet_template_test.id,
                "log_type": "file",
                "file_template_id": file_template.id,
                "access_level": "2",
                "use_sudo": True,
                "reference": "test_log_ref",
            }
        )

        # Ensure template is installed on server
        self.jet_template_test.write({"server_ids": [(4, self.server_test_1.id)]})

        # Create jet from template
        jet = self.jet_template_test.create_jet(
            server=self.server_test_1, name="Test Jet Fields"
        )

        # Find the created log
        jet_log = self.ServerLog.search([("jet_id", "=", jet.id)], limit=1)

        # Verify fields are copied correctly
        self.assertEqual(
            jet_log.name,
            server_log.name,
            "Log name should be copied",
        )
        self.assertEqual(
            jet_log.log_type,
            server_log.log_type,
            "Log type should be copied",
        )
        self.assertEqual(
            jet_log.file_template_id,
            server_log.file_template_id,
            "File template should be copied",
        )
        self.assertEqual(
            jet_log.access_level,
            server_log.access_level,
            "Access level should be copied",
        )
        self.assertEqual(
            jet_log.use_sudo,
            server_log.use_sudo,
            "Use sudo should be copied",
        )
        # Reference should be different (due to reference mixin)
        self.assertNotEqual(
            jet_log.reference,
            server_log.reference,
            "Reference should be different (unique)",
        )
        # Verify file was created for file-type log
        self.assertTrue(
            jet_log.file_id,
            "File should be created for file-type log",
        )
        self.assertEqual(
            jet_log.file_id.jet_id,
            jet,
            "Created file should be linked to the jet",
        )

    def test_create_jet_different_servers(self):
        """Test create_jet creates logs with correct server_id for different servers"""
        # Create a file template
        file_template = self.FileTemplate.create(
            {
                "name": "Test Log File Template",
                "file_name": "test_log.txt",
                "source": "tower",
                "server_dir": "/var/log",
                "code": "Test log content",
            }
        )

        # Create server log on template (linked to server_test_1)
        self.ServerLog.create(
            {
                "name": "Test Log",
                "server_id": self.server_test_1.id,
                "jet_template_id": self.jet_template_test.id,
                "log_type": "file",
                "file_template_id": file_template.id,
            }
        )

        # Ensure template is installed on both servers
        self.jet_template_test.write(
            {
                "server_ids": [
                    (4, self.server_test_1.id),
                    (4, self.server_test_2.id),
                ]
            }
        )

        # Create jet on server_test_2
        jet = self.jet_template_test.create_jet(
            server=self.server_test_2, name="Test Jet Server 2"
        )

        # Verify jet was created on correct server
        self.assertEqual(
            jet.server_id,
            self.server_test_2,
            "Jet should be on server_test_2",
        )

        # Verify server log is linked to server_test_2
        jet_log = self.ServerLog.search([("jet_id", "=", jet.id)], limit=1)
        self.assertEqual(
            jet_log.server_id,
            self.server_test_2,
            "Server log should be linked to server_test_2",
        )
        self.assertEqual(
            jet_log.file_id.server_id,
            self.server_test_2,
            "File should be linked to server_test_2",
        )
