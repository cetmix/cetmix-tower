# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import mute_logger

from .common_jets import TestTowerJetsCommon


class TestTowerJet(TestTowerJetsCommon):
    """
    Test the Jet model functionality
    """

    # All jet-related test data is now inherited from TestTowerJetsCommon

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   _on_is_available Tests
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def test_on_is_available_explicit_request_marked_processing_before_dispatch(self):
        """
        Regression: explicit request must be attached to the jet and set to
        processing before transition dispatch starts.

        We patch _bring_to_state (the actual dispatch) rather than
        _serve_jet_request so that _serve_jet_request runs for real and its
        side-effects (served_jet_request_id, request.state) are observable.
        A side_effect captures both values at the exact moment dispatch is
        triggered, proving ordering rather than just eventual state.
        """
        self.jet_test.write(
            {"state_id": self.state_initial.id, "target_state_id": False}
        )
        # Isolate the scenario: keep only the request created in this test.
        preexisting_new_requests = self.env["cx.tower.jet.request"].search(
            [("jet_id", "=", self.jet_test.id), ("state", "=", "new")]
        )
        if preexisting_new_requests:
            preexisting_new_requests.unlink()
        request = self.env["cx.tower.jet.request"].create(
            {
                "server_id": self.server_test_1.id,
                "jet_id": self.jet_test.id,
                "jet_template_id": self.jet_test.jet_template_id.id,
                "state_requested_id": self.state_running.id,
                "state": "new",
            }
        )

        # Capture the observable state of jet + request at dispatch time.
        observed = {}

        def capture(jet_self, target_state):
            jet_self.invalidate_recordset(["served_jet_request_id"])
            request.invalidate_recordset(["state"])
            observed["served_request_id"] = jet_self.served_jet_request_id.id
            observed["request_state"] = request.state

        with patch(
            "odoo.addons.cetmix_tower_server.models.cx_tower_jet.CxTowerJet._bring_to_state",
            autospec=True,
            side_effect=capture,
        ):
            self.jet_test._on_is_available()

        self.assertTrue(
            observed,
            "_bring_to_state must have been called; check that the request "
            "targets a different state than the jet's current state",
        )
        self.assertEqual(
            observed["served_request_id"],
            request.id,
            "Request must be saved to served_jet_request_id before dispatch",
        )
        self.assertEqual(
            observed["request_state"],
            "processing",
            "Request must be set to 'processing' before _bring_to_state is called",
        )

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   _compute_available_actions Tests
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def test_compute_available_actions_no_state(self):
        """
        Test _compute_available_actions when jet has no current state
        """
        # Jet has template but no state
        self.jet_test.state_id = False

        # action_available_ids should include only the create action
        self.assertEqual(
            len(self.jet_test.action_available_ids),
            1,
            "Available actions should include create action when jet has no state",
        )
        self.assertEqual(
            {action.id for action in self.jet_test.action_available_ids},
            {self.action_create.id},
            "Available action should be the create action",
        )

    def test_compute_available_actions_with_state_running(self):
        """
        Test _compute_available_actions when jet has state running.
        Create action is not available (no state_from_id); destroy and
        transition actions are available.
        """
        self.jet_test.state_id = self.state_running

        expected_actions = (
            self.action_running_to_stopped
            | self.action_running_to_error
            | self.action_destroy
        )
        actual_ids = {action.id for action in self.jet_test.action_available_ids}

        self.assertEqual(
            len(actual_ids),
            3,
            "Should have 3 available actions from running state",
        )
        self.assertNotIn(
            self.action_create.id,
            actual_ids,
            "Create action should not be available when jet has state",
        )
        self.assertIn(
            self.action_destroy.id,
            actual_ids,
            "Destroy action should be available",
        )
        self.assertEqual(
            actual_ids,
            {action.id for action in expected_actions},
            "Should have exact set: running_to_stopped, running_to_error, destroy",
        )

    def test_compute_available_actions_complex_scenario(self):
        """
        Test _compute_available_actions with complex scenario
        """
        # Use common actions from setup

        # Test different states
        test_cases = [
            (self.state_initial, [self.action_initial_to_running]),
            (
                self.state_running,
                [
                    self.action_running_to_stopped,
                    self.action_running_to_error,
                    self.action_destroy,
                ],
            ),
            (self.state_stopped, [self.action_stopped_to_running]),
            (self.state_error, [self.action_error_to_running]),
        ]

        for state, expected_actions in test_cases:
            self.jet_test.state_id = state
            actual_actions = self.jet_test.action_available_ids
            expected_actions_set = {action.id for action in expected_actions}
            actual_actions_set = {action.id for action in actual_actions}

            self.assertEqual(
                actual_actions_set,
                expected_actions_set,
                f"State {state.name} should have correct available actions",
            )

    def test_compute_available_actions_dependencies(self):
        """
        Test that _compute_available_actions has correct dependencies
        """
        # Use existing action from common setup
        action = self.action_running_to_stopped

        # Set initial state
        self.jet_test.state_id = self.state_running
        # Should have all actions from running state
        expected_actions = (
            self.action_running_to_stopped
            | self.action_running_to_error
            | self.action_destroy
        )
        self.assertEqual(
            {action.id for action in self.jet_test.action_available_ids},
            {action.id for action in expected_actions},
            "Should have all actions from running state initially",
        )

        # Change action's state_from_id (this should trigger recomputation)
        action.state_from_id = self.state_stopped

        # Jet should no longer have this specific action available
        # but should still have other actions from running state
        expected_remaining_actions = self.action_running_to_error | self.action_destroy
        self.assertEqual(
            {action.id for action in self.jet_test.action_available_ids},
            {action.id for action in expected_remaining_actions},
            "Should have remaining actions after changing one action's state_from_id",
        )

        # Change jet state to match action's new state_from_id
        self.jet_test.state_id = self.state_stopped

        # Now the modified action should be available again,
        # plus any other actions from stopped state
        expected_actions = action | self.action_stopped_to_running
        self.assertEqual(
            {action.id for action in self.jet_test.action_available_ids},
            {action.id for action in expected_actions},
            "Should have the modified action plus other actions from stopped state",
        )

    def test_compute_available_actions_cross_template_isolation(self):
        """
        Test that jets only see actions from their own template
        """
        # Create action for Odoo template
        odoo_action = self.JetAction.create(
            {
                "name": "Odoo Action",
                "reference": "odoo_action",
                "jet_template_id": self.jet_template_odoo.id,
                "state_from_id": self.state_running.id,
                "state_to_id": self.state_stopped.id,
                "state_transit_id": self.state_stopping.id,
                "priority": 10,
            }
        )

        # Create action for WordPress template
        wp_action = self.JetAction.create(
            {
                "name": "WordPress Action",
                "reference": "wordpress_action",
                "jet_template_id": self.jet_template_wordpress.id,
                "state_from_id": self.state_running.id,
                "state_to_id": self.state_stopped.id,
                "state_transit_id": self.state_stopping.id,
                "priority": 10,
            }
        )

        # Set both jets to running state
        self.jet_odoo.state_id = self.state_running
        self.jet_wordpress.state_id = self.state_running

        # Each jet should only see its own template's actions
        self.assertEqual(
            {action.id for action in self.jet_odoo.action_available_ids},
            {odoo_action.id},
            "Odoo jet should only see Odoo actions",
        )
        self.assertEqual(
            {action.id for action in self.jet_wordpress.action_available_ids},
            {wp_action.id},
            "WordPress jet should only see WordPress actions",
        )

        # Odoo jet should not see WordPress actions
        self.assertNotIn(
            wp_action.id,
            {action.id for action in self.jet_odoo.action_available_ids},
            "Odoo jet should not see WordPress actions",
        )
        # WordPress jet should not see Odoo actions
        self.assertNotIn(
            odoo_action.id,
            {action.id for action in self.jet_wordpress.action_available_ids},
            "WordPress jet should not see Odoo actions",
        )

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   Complex Template Hierarchy Tests
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def test_jet_template_domain_computation(self):
        """
        Test _compute_jet_template_domain method
        """
        # Test with server set
        jet_with_server = self.Jet.create(
            {
                "name": "Jet With Server",
                "reference": "jet_with_server",
                "jet_template_id": self.jet_template_test.id,
                "server_id": self.server_test_1.id,
            }
        )
        domain = jet_with_server.jet_template_domain
        expected_domain = [("server_ids", "in", [self.server_test_1.id])]
        self.assertEqual(domain, expected_domain, "Domain should include server filter")

        # Test domain computation with a different server
        server_test_2 = self.Server.create(
            {
                "name": "Test Server 2",
                "ip_v4_address": "192.168.1.2",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "host_key": "test_key_2",
                "os_id": self.os_debian_10.id,
            }
        )
        jet_with_different_server = self.Jet.create(
            {
                "name": "Jet With Different Server",
                "reference": "jet_with_different_server",
                "jet_template_id": self.jet_template_test.id,
                "server_id": server_test_2.id,
            }
        )
        domain = jet_with_different_server.jet_template_domain
        expected_domain = [("server_ids", "in", [server_test_2.id])]
        self.assertEqual(
            domain,
            expected_domain,
            "Domain should include server filter for different server",
        )

        # Test the domain computation method directly to verify the else branch
        # Create a temporary jet object to test the method without saving
        temp_jet = self.Jet.new(
            {
                "name": "Temp Jet",
                "jet_template_id": self.jet_template_test.id,
                "server_id": False,
            }
        )
        temp_jet._compute_jet_template_domain()
        self.assertEqual(
            temp_jet.jet_template_domain,
            [],
            "Domain should be empty when server_id is False",
        )

    def test_jet_requires_ids_computation(self):
        """
        Test _compute_jet_requires_ids method with complex dependencies
        """
        # Test Odoo jet dependencies
        odoo_deps = self.jet_odoo.jet_requires_ids
        self.assertEqual(
            len(odoo_deps), 2, "Odoo jet should have 2 direct dependencies"
        )

        # Check that dependencies are for postgres and nginx
        dep_template_ids = odoo_deps.mapped(
            "jet_template_dependency_id.template_required_id.id"
        )
        expected_ids = {self.jet_template_postgres.id, self.jet_template_nginx.id}
        self.assertEqual(
            set(dep_template_ids), expected_ids, "Should depend on postgres and nginx"
        )

        # Test WooCommerce jet dependencies
        # (should include both Odoo and WordPress deps)
        woocommerce_deps = self.jet_woocommerce.jet_requires_ids
        self.assertEqual(
            len(woocommerce_deps),
            2,
            "WooCommerce jet should have 2 direct dependencies",
        )

        # Check that dependencies are for wordpress and odoo
        dep_template_ids = woocommerce_deps.mapped(
            "jet_template_dependency_id.template_required_id.id"
        )
        expected_ids = {self.jet_template_wordpress.id, self.jet_template_odoo.id}
        self.assertEqual(
            set(dep_template_ids), expected_ids, "Should depend on wordpress and odoo"
        )

    def test_jet_limit_per_server_same_server_rejected(self):
        """Constraint rejects creating more jets than template limit per server."""
        template = self.JetTemplate.create(
            {
                "name": "Template With Limit",
                "reference": "template_with_limit",
                "limit_per_server": 1,
            }
        )
        self.Jet.create(
            {
                "name": "Limited Jet 1",
                "reference": "limited_jet_1",
                "jet_template_id": template.id,
                "server_id": self.server_test_1.id,
            }
        )

        with self.assertRaisesRegex(ValidationError, "Jet limit per server reached"):
            self.Jet.create(
                {
                    "name": "Limited Jet 2",
                    "reference": "limited_jet_2",
                    "jet_template_id": template.id,
                    "server_id": self.server_test_1.id,
                }
            )

    def test_jet_limit_per_server_different_servers_allowed(self):
        """
        Constraint allows same template on different servers
        but within per-server limit.
        """
        template = self.JetTemplate.create(
            {
                "name": "Template With Per-Server Limit",
                "reference": "template_with_per_server_limit",
                "limit_per_server": 1,
            }
        )
        server_test_2 = self.Server.create(
            {
                "name": "Jet Limit Test Server 2",
                "ip_v4_address": "192.168.1.22",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "host_key": "jet_limit_test_server_2_key",
                "os_id": self.os_debian_10.id,
            }
        )

        jet_on_server_1 = self.Jet.create(
            {
                "name": "Limited Jet Server 1",
                "reference": "limited_jet_server_1",
                "jet_template_id": template.id,
                "server_id": self.server_test_1.id,
            }
        )
        jet_on_server_2 = self.Jet.create(
            {
                "name": "Limited Jet Server 2",
                "reference": "limited_jet_server_2",
                "jet_template_id": template.id,
                "server_id": server_test_2.id,
            }
        )

        self.assertTrue(
            jet_on_server_1.exists(), "Jet on first server should be created"
        )
        self.assertTrue(
            jet_on_server_2.exists(), "Jet on second server should be created"
        )

    def test_jet_requires_ids_template_change(self):
        """
        Test _compute_jet_requires_ids for different templates
        """
        # Create jets for different templates
        jet_tower_core = self.Jet.create(
            {
                "name": "Tower Core Jet",
                "reference": "tower_core_jet",
                "jet_template_id": self.jet_template_tower_core.id,
                "server_id": self.server_test_1.id,
            }
        )
        self.assertEqual(
            len(jet_tower_core.jet_requires_ids),
            0,
            "Tower core should have no dependencies",
        )

        jet_odoo = self.Jet.create(
            {
                "name": "Odoo Jet Test",
                "reference": "odoo_jet_test",
                "jet_template_id": self.jet_template_odoo.id,
                "server_id": self.server_test_1.id,
            }
        )
        self.assertEqual(
            len(jet_odoo.jet_requires_ids), 2, "Odoo should have 2 dependencies"
        )

        jet_woocommerce = self.Jet.create(
            {
                "name": "WooCommerce Jet Test",
                "reference": "woocommerce_jet_test",
                "jet_template_id": self.jet_template_woocommerce_odoo.id,
                "server_id": self.server_test_1.id,
            }
        )
        self.assertEqual(
            len(jet_woocommerce.jet_requires_ids),
            2,
            "WooCommerce should have 2 dependencies",
        )

    def test_jet_requires_ids_dependency_removal(self):
        """
        Test _compute_jet_requires_ids when template dependencies are removed
        """
        # Create jet with Odoo template
        jet_odoo = self.Jet.create(
            {
                "name": "Odoo Jet Test",
                "reference": "odoo_jet_test",
                "jet_template_id": self.jet_template_odoo.id,
                "server_id": self.server_test_1.id,
            }
        )
        initial_deps = len(jet_odoo.jet_requires_ids)
        self.assertEqual(initial_deps, 2, "Should have 2 dependencies initially")

        # Remove one dependency from template
        postgres_dep = self.JetTemplateDependency.search(
            [
                ("template_id", "=", self.jet_template_odoo.id),
                ("template_required_id", "=", self.jet_template_postgres.id),
            ]
        )
        postgres_dep.unlink()

        # Jet dependencies should be updated
        self.assertEqual(
            len(jet_odoo.jet_requires_ids), 1, "Should have 1 dependency after removal"
        )
        remaining_dep = jet_odoo.jet_requires_ids[0]
        self.assertEqual(
            remaining_dep.jet_template_dependency_id.template_required_id,
            self.jet_template_nginx,
            "Remaining dependency should be nginx",
        )

    def test_jet_requires_ids_dependency_addition(self):
        """
        Test _compute_jet_requires_ids when template dependencies are added
        """
        # Create jet with tower core (no dependencies)
        jet_tower_core = self.Jet.create(
            {
                "name": "Tower Core Jet",
                "reference": "tower_core_jet",
                "jet_template_id": self.jet_template_tower_core.id,
                "server_id": self.server_test_1.id,
            }
        )
        self.assertEqual(
            len(jet_tower_core.jet_requires_ids),
            0,
            "Should have no dependencies initially",
        )

        # Add dependency to tower core
        # (use a template that won't create circular dependency)
        new_dep = self.JetTemplateDependency.create(
            {
                "template_id": self.jet_template_tower_core.id,
                "template_required_id": self.jet_template_test.id,
                "state_required_id": self.state_running.id,
            }
        )

        # Jet dependencies should be updated
        self.assertEqual(
            len(jet_tower_core.jet_requires_ids),
            1,
            "Should have 1 dependency after addition",
        )
        added_dep = jet_tower_core.jet_requires_ids[0]
        self.assertEqual(
            added_dep.jet_template_dependency_id,
            new_dep,
            "Added dependency should match the new dependency",
        )

    def test_jet_requires_ids_multiple_jets_same_template(self):
        """
        Test _compute_jet_requires_ids with multiple jets using same template
        """
        # Create another Odoo jet
        jet_odoo_2 = self.Jet.create(
            {
                "name": "Odoo Jet 2",
                "reference": "odoo_jet_2",
                "jet_template_id": self.jet_template_odoo.id,
                "server_id": self.server_test_1.id,
            }
        )

        # Both jets should have same dependencies
        deps_1 = self.jet_odoo.jet_requires_ids
        deps_2 = jet_odoo_2.jet_requires_ids

        self.assertEqual(
            len(deps_1),
            len(deps_2),
            "Both jets should have same number of dependencies",
        )

        # Check that dependencies are the same
        deps_1_template_ids = deps_1.mapped(
            "jet_template_dependency_id.template_required_id.id"
        )
        deps_2_template_ids = deps_2.mapped(
            "jet_template_dependency_id.template_required_id.id"
        )
        self.assertEqual(
            set(deps_1_template_ids),
            set(deps_2_template_ids),
            "Both jets should have same dependency templates",
        )

    def test_jet_requires_ids_consistency_with_template(self):
        """
        Test that jet dependencies are consistent with template dependencies
        """
        # Test with different templates
        templates_to_test = [
            (self.jet_template_tower_core, 0),
            (self.jet_template_docker, 1),
            (self.jet_template_nginx, 1),
            (self.jet_template_postgres, 1),
            (self.jet_template_mariadb, 1),
            (self.jet_template_odoo, 2),
            (self.jet_template_wordpress, 2),
            (self.jet_template_woocommerce_odoo, 2),
        ]

        for template, expected_dep_count in templates_to_test:
            # Create a jet with this template
            test_jet = self.Jet.create(
                {
                    "name": f"Test Jet for {template.name}",
                    "reference": f"test_jet_{template.reference}",
                    "jet_template_id": template.id,
                    "server_id": self.server_test_1.id,
                }
            )

            # Check dependency count
            actual_dep_count = len(test_jet.jet_requires_ids)
            self.assertEqual(
                actual_dep_count,
                expected_dep_count,
                f"{template.name} should have {expected_dep_count} "
                f"dependencies, got {actual_dep_count}",
            )

            # Verify that all jet dependencies correspond to template dependencies
            template_deps = template.template_requires_ids
            jet_deps = test_jet.jet_requires_ids

            if template_deps:
                self.assertEqual(
                    len(jet_deps),
                    len(template_deps),
                    "Jet dependencies count should match"
                    f" template dependencies for {template.name}",
                )

                # Check that each jet dependency corresponds to a template dependency
                jet_dep_template_ids = jet_deps.mapped("jet_template_dependency_id.id")
                template_dep_ids = template_deps.ids
                self.assertEqual(
                    set(jet_dep_template_ids),
                    set(template_dep_ids),
                    "Jet dependencies should match template"
                    f" dependencies for {template.name}",
                )

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   bring_to_state Tests
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def test_bring_to_state_success_user_level(self):
        """
        Test bring_to_state succeeds when user has sufficient access level.
        User (level 1) can access state with level 1.
        """
        # Use existing state and set it to User access level (1)
        self.state_running.access_level = "1"
        self.state_running.invalidate_recordset(["access_level"])

        # Ensure user has access to the jet
        self.jet_test.write({"user_ids": [(4, self.user.id)]})
        self.server_test_1.write({"user_ids": [(4, self.user.id)]})

        # Set jet to initial state
        self.jet_test.write({"state_id": self.state_initial.id})
        self.jet_test.invalidate_recordset(["state_id"])

        # User should be able to bring jet to user-level state
        self.jet_test.with_user(self.user).with_context(
            cetmix_tower_no_commit=True
        ).bring_to_state("test_running")
        self.assertEqual(
            self.jet_test.state_id,
            self.state_running,
            "Jet should be brought to user-level state by user",
        )

    def test_bring_to_state_success_manager_level(self):
        """
        Test bring_to_state succeeds when manager has sufficient access level.
        Manager (level 2) can access state with level 2.
        """
        # Use existing state and set it to Manager access level (2)
        self.state_stopped.access_level = "2"
        self.state_stopped.invalidate_recordset(["access_level"])

        # Ensure manager has access to the jet
        self.jet_test.write({"manager_ids": [(4, self.manager.id)]})
        self.server_test_1.write({"manager_ids": [(4, self.manager.id)]})

        # Set jet to running state (which has action to stopped)
        self.jet_test.write({"state_id": self.state_running.id})
        self.jet_test.invalidate_recordset(["state_id"])

        # Manager should be able to bring jet to manager-level state
        self.jet_test.with_user(self.manager).with_context(
            cetmix_tower_no_commit=True
        ).bring_to_state("test_stopped")
        self.assertEqual(
            self.jet_test.state_id,
            self.state_stopped,
            "Jet should be brought to manager-level state by manager",
        )

    def test_bring_to_state_success_root_level(self):
        """
        Test bring_to_state succeeds when root has sufficient access level.
        Root (level 3) can access state with level 3.
        """
        # Use existing state and set it to Root access level (3)
        self.state_error.access_level = "3"
        self.state_error.invalidate_recordset(["access_level"])

        # Root has full access, but ensure access for consistency
        self.jet_test.write({"manager_ids": [(4, self.root.id)]})
        self.server_test_1.write({"manager_ids": [(4, self.root.id)]})

        # Set jet to running state (which has action to error)
        self.jet_test.write({"state_id": self.state_running.id})
        self.jet_test.invalidate_recordset(["state_id"])

        # Root should be able to bring jet to root-level state
        self.jet_test.with_user(self.root).with_context(
            cetmix_tower_no_commit=True
        ).bring_to_state("test_error")
        self.assertEqual(
            self.jet_test.state_id,
            self.state_error,
            "Jet should be brought to root-level state by root",
        )

    def test_bring_to_state_access_error_user_to_manager(self):
        """
        Test bring_to_state raises AccessError when user (level 1)
        tries to access manager-level state (level 2).
        """
        # Use existing state and set it to Manager access level (2)
        self.state_stopped.access_level = "2"
        self.state_stopped.invalidate_recordset(["access_level"])

        # Ensure user has access to the jet (for the access check to work)
        self.jet_test.write({"user_ids": [(4, self.user.id)]})
        self.server_test_1.write({"user_ids": [(4, self.user.id)]})

        # Set jet to running state (which has action to stopped)
        self.jet_test.write({"state_id": self.state_running.id})
        self.jet_test.invalidate_recordset(["state_id"])

        # User should not be able to bring jet to manager-level state
        with self.assertRaises(AccessError) as context:
            self.jet_test.with_user(self.user).with_context(
                cetmix_tower_no_commit=True
            ).bring_to_state("test_stopped")

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

    def test_bring_to_state_access_error_user_to_root(self):
        """
        Test bring_to_state raises AccessError when user (level 1)
        tries to access root-level state (level 3).
        """
        # Use existing state and set it to Root access level (3)
        self.state_error.access_level = "3"
        self.state_error.invalidate_recordset(["access_level"])

        # Ensure user has access to the jet (for the access check to work)
        self.jet_test.write({"user_ids": [(4, self.user.id)]})
        self.server_test_1.write({"user_ids": [(4, self.user.id)]})

        # Set jet to running state (which has action to error)
        self.jet_test.write({"state_id": self.state_running.id})
        self.jet_test.invalidate_recordset(["state_id"])

        # User should not be able to bring jet to root-level state
        with self.assertRaises(AccessError) as context:
            self.jet_test.with_user(self.user).with_context(
                cetmix_tower_no_commit=True
            ).bring_to_state("test_error")

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

    def test_bring_to_state_access_error_manager_to_root(self):
        """
        Test bring_to_state raises AccessError when manager (level 2)
        tries to access root-level state (level 3).
        """
        # Use existing state and set it to Root access level (3)
        self.state_error.access_level = "3"
        self.state_error.invalidate_recordset(["access_level"])

        # Ensure manager has access to the jet (for the access check to work)
        self.jet_test.write({"manager_ids": [(4, self.manager.id)]})
        self.server_test_1.write({"manager_ids": [(4, self.manager.id)]})

        # Set jet to running state (which has action to error)
        self.jet_test.write({"state_id": self.state_running.id})
        self.jet_test.invalidate_recordset(["state_id"])

        # Manager should not be able to bring jet to root-level state
        with self.assertRaises(AccessError) as context:
            self.jet_test.with_user(self.manager).with_context(
                cetmix_tower_no_commit=True
            ).bring_to_state("test_error")

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

    def test_bring_to_state_manager_can_access_user_level(self):
        """
        Test bring_to_state succeeds when manager (level 2) who IS in manager_ids
        accesses user-level state (level 1).
        Higher access levels can access lower level states.
        """
        # Use existing state and set it to User access level (1)
        self.state_running.access_level = "1"
        self.state_running.invalidate_recordset(["access_level"])

        # Ensure manager has access to the jet
        # Manager IS in manager_ids, so they keep their manager access level (2)
        self.jet_test.write({"manager_ids": [(4, self.manager.id)]})
        self.server_test_1.write({"manager_ids": [(4, self.manager.id)]})

        # Set jet to initial state
        self.jet_test.write({"state_id": self.state_initial.id})
        self.jet_test.invalidate_recordset(["state_id"])

        # Manager should be able to bring jet to user-level state
        self.jet_test.with_user(self.manager).with_context(
            cetmix_tower_no_commit=True
        ).bring_to_state("test_running")
        self.assertEqual(
            self.jet_test.state_id,
            self.state_running,
            "Manager should be able to access user-level state",
        )

    def test_bring_to_state_manager_not_in_manager_ids_treated_as_user(self):
        """
        Test bring_to_state treats manager (level 2) who is NOT in manager_ids
        as user (level 1).
        Manager should be able to set user-level state but not manager-level state.
        """
        # Use existing state and set it to User access level (1)
        self.state_running.access_level = "1"
        self.state_running.invalidate_recordset(["access_level"])

        # Ensure manager has access to the jet via user_ids but NOT via manager_ids
        self.jet_test.write({"user_ids": [(4, self.manager.id)]})
        self.server_test_1.write({"user_ids": [(4, self.manager.id)]})
        # Explicitly ensure manager is NOT in manager_ids
        self.jet_test.write({"manager_ids": [(5, 0, 0)]})

        # Set jet to initial state
        self.jet_test.write({"state_id": self.state_initial.id})
        self.jet_test.invalidate_recordset(["state_id"])

        # Manager (treated as user) should be able to bring jet to user-level state
        self.jet_test.with_user(self.manager).with_context(
            cetmix_tower_no_commit=True
        ).bring_to_state("test_running")
        self.assertEqual(
            self.jet_test.state_id,
            self.state_running,
            "Manager not in manager_ids should be able to access user-level state",
        )

    def test_bring_to_state_manager_not_in_manager_ids_cannot_access_manager_level(
        self,
    ):
        """
        Test bring_to_state raises AccessError when manager (level 2) who is NOT
        in manager_ids tries to access manager-level state (level 2).
        Manager should be treated as user (level 1) and cannot access level 2.
        """
        # Use existing state and set it to Manager access level (2)
        self.state_stopped.access_level = "2"
        self.state_stopped.invalidate_recordset(["access_level"])

        # Ensure manager has access to the jet via user_ids but NOT via manager_ids
        self.jet_test.write({"user_ids": [(4, self.manager.id)]})
        self.server_test_1.write({"user_ids": [(4, self.manager.id)]})
        # Explicitly ensure manager is NOT in manager_ids
        self.jet_test.write({"manager_ids": [(5, 0, 0)]})

        # Set jet to running state (which has action to stopped)
        self.jet_test.write({"state_id": self.state_running.id})
        self.jet_test.invalidate_recordset(["state_id"])

        # Manager (treated as user) should not be able to bring jet
        # to manager-level state
        with self.assertRaises(AccessError) as context:
            self.jet_test.with_user(self.manager).with_context(
                cetmix_tower_no_commit=True
            ).bring_to_state("test_stopped")

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

    def test_bring_to_state_root_can_access_manager_level(self):
        """
        Test bring_to_state succeeds when root (level 3)
        accesses manager-level state (level 2).
        Higher access levels can access lower level states.
        """
        # Use existing state and set it to Manager access level (2)
        self.state_stopped.access_level = "2"
        self.state_stopped.invalidate_recordset(["access_level"])

        # Root has full access, but ensure access for consistency
        self.jet_test.write({"manager_ids": [(4, self.root.id)]})
        self.server_test_1.write({"manager_ids": [(4, self.root.id)]})

        # Set jet to running state (which has action to stopped)
        self.jet_test.write({"state_id": self.state_running.id})
        self.jet_test.invalidate_recordset(["state_id"])

        # Root should be able to bring jet to manager-level state
        self.jet_test.with_user(self.root).with_context(
            cetmix_tower_no_commit=True
        ).bring_to_state("test_stopped")
        self.assertEqual(
            self.jet_test.state_id,
            self.state_stopped,
            "Root should be able to access manager-level state",
        )

    def test_bring_to_state_invalid_reference(self):
        """
        Test bring_to_state raises ValidationError when state reference is invalid.
        """
        # Set jet to initial state
        self.jet_test.state_id = self.state_initial

        # Should raise ValidationError for invalid state reference
        with self.assertRaises(ValidationError) as context:
            self.jet_test.with_context(cetmix_tower_no_commit=True).bring_to_state(
                "invalid_state_reference"
            )

        self.assertIn(
            "State 'invalid_state_reference' not found",
            str(context.exception),
            "Should raise ValidationError with appropriate message",
        )
        self.assertIn(
            self.jet_test.display_name,
            str(context.exception),
            "Error message should include jet display name",
        )

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   _get_user_effective_access_level Tests
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def test_get_user_effective_access_level_user(self):
        """
        Test _get_user_effective_access_level returns "1" for user.
        """
        # Ensure user has access to the jet
        self.jet_test.write({"user_ids": [(4, self.user.id)]})

        # User should have effective access level "1"
        effective_level = self.jet_test.with_user(
            self.user
        )._get_user_effective_access_level()
        self.assertEqual(
            effective_level,
            "1",
            "User should have effective access level 1",
        )

    def test_get_user_effective_access_level_manager_in_manager_ids(self):
        """
        Test _get_user_effective_access_level returns "2" for manager
        who IS in manager_ids.
        """
        # Ensure manager has access to the jet and IS in manager_ids
        self.jet_test.write({"manager_ids": [(4, self.manager.id)]})

        # Manager in manager_ids should have effective access level "2"
        effective_level = self.jet_test.with_user(
            self.manager
        )._get_user_effective_access_level()
        self.assertEqual(
            effective_level,
            "2",
            "Manager in manager_ids should have effective access level 2",
        )

    def test_get_user_effective_access_level_manager_not_in_manager_ids(self):
        """
        Test _get_user_effective_access_level returns "1" for manager
        who is NOT in manager_ids (downgraded to user level).
        """
        # Ensure manager has access to the jet via user_ids but NOT via manager_ids
        self.jet_test.write({"user_ids": [(4, self.manager.id)]})
        # Explicitly ensure manager is NOT in manager_ids
        self.jet_test.write({"manager_ids": [(5, 0, 0)]})

        # Manager not in manager_ids should have effective access level "1"
        effective_level = self.jet_test.with_user(
            self.manager
        )._get_user_effective_access_level()
        self.assertEqual(
            effective_level,
            "1",
            "Manager not in manager_ids should have effective access level 1",
        )

    def test_get_user_effective_access_level_root(self):
        """
        Test _get_user_effective_access_level returns "3" for root.
        """
        # Root should have effective access level "3" regardless of manager_ids
        effective_level = self.jet_test.with_user(
            self.root
        )._get_user_effective_access_level()
        self.assertEqual(
            effective_level,
            "3",
            "Root should have effective access level 3",
        )

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   unlink Tests
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def test_unlink_deletable_jet_with_files(self):
        """
        Test unlink succeeds when jet is deletable and has files.
        Files should be unlinked after the jet is deleted.
        """
        # Create a deletable jet (deletable defaults to True)
        jet = self._create_jet(
            "Deletable Jet",
            "deletable_jet",
        )

        # Create files linked to the jet
        file1 = self.File.create(
            {
                "name": "test_file_1.txt",
                "source": "tower",
                "server_id": self.server_test_1.id,
                "server_dir": "/tmp",
                "jet_id": jet.id,
                "file_type": "text",
            }
        )
        file2 = self.File.create(
            {
                "name": "test_file_2.txt",
                "source": "tower",
                "server_id": self.server_test_1.id,
                "server_dir": "/tmp",
                "jet_id": jet.id,
                "file_type": "text",
            }
        )

        # Verify files exist
        self.assertEqual(len(jet.file_ids), 2, "Jet should have 2 files")
        self.assertIn(file1, jet.file_ids, "File 1 should be linked to jet")
        self.assertIn(file2, jet.file_ids, "File 2 should be linked to jet")

        # Store file IDs before deletion
        file_ids = {file1.id, file2.id}

        # Unlink the jet
        jet.unlink()

        # Verify jet is deleted
        self.assertFalse(jet.exists(), "Jet should be deleted")

        # Verify files are also deleted
        remaining_files = self.File.browse(list(file_ids))
        self.assertFalse(
            remaining_files.exists(),
            "Files should be unlinked after jet deletion",
        )

    def test_unlink_deletable_jet_without_files(self):
        """
        Test unlink succeeds when jet is deletable but has no files.
        """
        # Create a deletable jet without files (deletable defaults to True)
        jet = self._create_jet(
            "Deletable Jet No Files",
            "deletable_jet_no_files",
        )

        # Verify jet has no files
        self.assertEqual(len(jet.file_ids), 0, "Jet should have no files")

        # Unlink the jet
        jet.unlink()

        # Verify jet is deleted
        self.assertFalse(jet.exists(), "Jet should be deleted")

    def test_unlink_not_deletable_jet_raises_error(self):
        """
        Test unlink raises ValidationError when jet is not deletable.
        """
        # Create a non-deletable jet
        jet = self._create_jet(
            "Not Deletable Jet",
            "not_deletable_jet",
        )
        jet.write({"deletable": False})

        # Attempt to unlink should raise ValidationError
        with self.assertRaises(ValidationError) as context:
            jet.unlink()

        # Verify error message contains jet display name
        self.assertIn(
            "cannot be deleted",
            str(context.exception),
            "Error message should mention deletion restriction",
        )
        self.assertIn(
            jet.display_name,
            str(context.exception),
            "Error message should include jet display name",
        )

        # Verify jet still exists
        self.assertTrue(jet.exists(), "Jet should not be deleted")

    def test_unlink_multiple_jets_mixed_deletable(self):
        """
        Test unlink with multiple jets where some are deletable and some are not.
        Should raise ValidationError listing non-deletable jets.
        """
        # Create deletable jet (deletable defaults to True)
        deletable_jet = self._create_jet(
            "Deletable Jet",
            "deletable_jet_multi",
        )

        # Create non-deletable jet
        not_deletable_jet = self._create_jet(
            "Not Deletable Jet",
            "not_deletable_jet_multi",
        )
        not_deletable_jet.write({"deletable": False})

        # Attempt to unlink both should raise ValidationError
        jets = deletable_jet | not_deletable_jet
        with self.assertRaises(ValidationError) as context:
            jets.unlink()

        # Verify error message contains non-deletable jet display name
        self.assertIn(
            "cannot be deleted",
            str(context.exception),
            "Error message should mention deletion restriction",
        )
        self.assertIn(
            not_deletable_jet.display_name,
            str(context.exception),
            "Error message should include non-deletable jet display name",
        )

        # Verify both jets still exist
        self.assertTrue(deletable_jet.exists(), "Deletable jet should not be deleted")
        self.assertTrue(
            not_deletable_jet.exists(), "Non-deletable jet should not be deleted"
        )

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   create_waypoint Tests
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def test_create_waypoint_with_record_template(self):
        """
        Test create_waypoint with waypoint template record
        """
        # Get the default name from the helper function
        default_vals = self.jet_test._prepare_waypoint_values(
            self.waypoint_template, name=None
        )
        expected_default_name = default_vals["name"]

        # Create waypoint using template record
        waypoint = self.jet_test.create_waypoint(self.waypoint_template)

        # Should return a waypoint record
        self.assertTrue(waypoint, "Should return a waypoint record")
        self.assertTrue(waypoint.exists(), "Waypoint should exist")
        self.assertEqual(
            waypoint.jet_id.id,
            self.jet_test.id,
            "Waypoint should belong to the jet",
        )
        self.assertEqual(
            waypoint.waypoint_template_id.id,
            self.waypoint_template.id,
            "Waypoint should use the correct template",
        )
        self.assertEqual(
            waypoint.name,
            expected_default_name,
            "Waypoint should have default name from helper function",
        )
        # Reference is auto-generated, so just verify it exists and is not empty
        self.assertTrue(
            waypoint.reference,
            "Waypoint should have an auto-generated reference",
        )

    def test_create_waypoint_with_string_reference(self):
        """
        Test create_waypoint with waypoint template string reference
        """
        # Use the template's reference (mandatory field, always present)
        template_reference = self.waypoint_template.reference

        # Create waypoint using string reference
        waypoint = self.jet_test.create_waypoint(template_reference)

        # Should return a waypoint record
        self.assertTrue(waypoint, "Should return a waypoint record")
        self.assertTrue(waypoint.exists(), "Waypoint should exist")
        self.assertEqual(
            waypoint.waypoint_template_id.id,
            self.waypoint_template.id,
            "Waypoint should use the correct template from reference",
        )
        # Reference is auto-generated, so just verify it exists and is not empty
        self.assertTrue(
            waypoint.reference,
            "Waypoint should have an auto-generated reference",
        )

    def test_create_waypoint_with_name(self):
        """
        Test create_waypoint with custom name
        """
        # Create waypoint with custom name
        waypoint = self.jet_test.create_waypoint(
            self.waypoint_template, name="Custom Waypoint Name"
        )

        # Should return a waypoint record with custom name
        self.assertTrue(waypoint, "Should return a waypoint record")
        self.assertEqual(
            waypoint.name,
            "Custom Waypoint Name",
            "Waypoint should have the custom name",
        )
        # Reference is auto-generated, so just verify it exists and is not empty
        self.assertTrue(
            waypoint.reference,
            "Waypoint should have an auto-generated reference",
        )

    def test_create_waypoint_with_fly_here(self):
        """
        Test create_waypoint with fly_here parameter
        Note: fly_here should set is_destination=True, and after prepare()
        the waypoint should automatically fly to if is_destination is True
        """
        # Create waypoint with fly_here=True
        waypoint = self.jet_test.create_waypoint(self.waypoint_template, fly_here=True)

        # Should return a waypoint record
        self.assertTrue(waypoint, "Should return a waypoint record")
        self.assertTrue(waypoint.exists(), "Waypoint should exist")

        # Verify that the waypoint flew to
        # (state should be "current" in synchronous tests)
        self.assertEqual(
            waypoint.state,
            "current",
            "Waypoint should have flown to and "
            "become current (tests run synchronously)",
        )

        # Verify jet's waypoint_id was updated
        self.assertEqual(
            self.jet_test.waypoint_id.id,
            waypoint.id,
            "Jet's waypoint_id should be updated to the flown-to waypoint",
        )

    @mute_logger("odoo.addons.cetmix_tower_server.models.cx_tower_jet")
    def test_create_waypoint_jet_busy(self):
        """
        Test create_waypoint when jet is busy (has target_state_id)
        """
        # Set jet to busy state (has target_state_id)
        self.jet_test.target_state_id = self.state_running

        # Try to create waypoint
        with self.assertRaises(ValidationError):
            self.jet_test.create_waypoint(self.waypoint_template)

    @mute_logger("odoo.addons.cetmix_tower_server.models.cx_tower_jet")
    def test_create_waypoint_template_not_found(self):
        """
        Test create_waypoint with non-existent template reference
        """
        # Mute logger error for this test
        with self.assertRaises(ValidationError):
            self.jet_test.create_waypoint("non_existent_reference")

    @mute_logger("odoo.addons.cetmix_tower_server.models.cx_tower_jet")
    def test_create_waypoint_template_wrong_jet_template(self):
        """
        Test create_waypoint with template from different jet template
        """
        # Create a waypoint template for a different jet template
        other_jet_template = self.JetTemplate.create(
            {
                "name": "Other Jet Template",
                "reference": "other_jet_template",
            }
        )
        other_waypoint_template = self.JetWaypointTemplate.create(
            {
                "name": "Other Waypoint Template",
                "jet_template_id": other_jet_template.id,
            }
        )

        # Mute logger error for this test
        with self.assertRaises(ValidationError):
            # Try to create waypoint with template from different jet template
            self.jet_test.create_waypoint(other_waypoint_template)

    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    #   Create a Waypoint command (flight plan) tests
    # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

    def test_create_waypoint_command_success_fly_here_false(self):
        """Create a Waypoint command from flight plan: waypoint created, log
        finished by callback."""
        command = self.Command.create(
            {
                "name": "Create waypoint command",
                "action": "create_waypoint",
                "waypoint_template_id": self.waypoint_template.id,
                "fly_here": False,
            }
        )
        plan = self.Plan.create({"name": "Plan create waypoint"})
        self.plan_line.create(
            {
                "plan_id": plan.id,
                "sequence": 10,
                "command_id": command.id,
            }
        )
        initial_waypoint_count = len(self.jet_test.waypoint_ids)
        plan_log = self.server_test_1.sudo().run_flight_plan(plan, jet=self.jet_test)
        self.assertTrue(plan_log, "Plan log should be created")
        command_logs = plan_log.command_log_ids.filtered(
            lambda log: log.command_id == command
        )
        self.assertEqual(
            len(command_logs), 1, "Exactly one command log for create_waypoint"
        )
        log_record = command_logs[0]
        self.assertTrue(
            log_record.finish_date,
            "Command log should be finished by waypoint callback",
        )
        self.assertEqual(
            log_record.command_status,
            0,
            "Command should finish with success",
        )
        self.assertEqual(
            len(self.jet_test.waypoint_ids),
            initial_waypoint_count + 1,
            "One new waypoint should be created",
        )
        new_waypoint = self.jet_test.waypoint_ids.filtered(
            lambda w: w.created_from_command_log_id == log_record
        )
        self.assertEqual(len(new_waypoint), 1, "One waypoint linked to command log")
        new_waypoint = new_waypoint[0]
        self.assertEqual(
            new_waypoint.state,
            "ready",
            "Waypoint should be in ready state (fly_here=False)",
        )
        self.assertEqual(
            new_waypoint.created_from_command_log_id,
            log_record,
            "Waypoint should reference the command log",
        )

    def test_create_waypoint_command_success_fly_here_true(self):
        """Create a Waypoint command with fly_here: waypoint becomes current."""
        command = self.Command.create(
            {
                "name": "Create waypoint fly here",
                "action": "create_waypoint",
                "waypoint_template_id": self.waypoint_template.id,
                "fly_here": True,
            }
        )
        plan = self.Plan.create({"name": "Plan create waypoint fly here"})
        self.plan_line.create(
            {
                "plan_id": plan.id,
                "sequence": 10,
                "command_id": command.id,
            }
        )
        plan_log = self.server_test_1.sudo().run_flight_plan(plan, jet=self.jet_test)
        command_logs = plan_log.command_log_ids.filtered(
            lambda log: log.command_id == command
        )
        log_record = command_logs[0]
        self.assertTrue(log_record.finish_date, "Command log should be finished")
        self.assertEqual(log_record.command_status, 0, "Command should succeed")
        waypoints_with_log = self.jet_test.waypoint_ids.filtered(
            lambda w: w.created_from_command_log_id == log_record
        )
        self.assertEqual(
            len(waypoints_with_log),
            1,
            "One waypoint created from command",
        )
        self.assertEqual(
            waypoints_with_log.state,
            "current",
            "Waypoint should be current when fly_here=True",
        )
        self.assertEqual(
            self.jet_test.waypoint_id,
            waypoints_with_log,
            "Jet waypoint_id should point to the new waypoint",
        )

    def test_create_waypoint_command_no_jet(self):
        """Create a Waypoint command run without jet: command log finished
        with JET_NOT_FOUND."""
        from ..models.constants import JET_NOT_FOUND

        command = self.Command.create(
            {
                "name": "Create waypoint no jet",
                "action": "create_waypoint",
                "waypoint_template_id": self.waypoint_template.id,
                "fly_here": False,
            }
        )
        plan = self.Plan.create({"name": "Plan no jet"})
        self.plan_line.create(
            {"plan_id": plan.id, "sequence": 10, "command_id": command.id}
        )
        plan_log = self.server_test_1.sudo().run_flight_plan(plan)
        command_logs = plan_log.command_log_ids.filtered(
            lambda log: log.command_id == command
        )
        self.assertEqual(len(command_logs), 1)
        self.assertEqual(
            command_logs.command_status,
            JET_NOT_FOUND,
            "Should finish with JET_NOT_FOUND when no jet in plan",
        )
        self.assertTrue(command_logs.finish_date)

    def test_create_waypoint_command_no_template(self):
        """Create a Waypoint command without waypoint template:
        WAYPOINT_TEMPLATE_NOT_FOUND."""
        from ..models.constants import WAYPOINT_TEMPLATE_NOT_FOUND

        command = self.Command.create(
            {
                "name": "Create waypoint no template",
                "action": "create_waypoint",
                "fly_here": False,
            }
        )
        plan = self.Plan.create({"name": "Plan no template"})
        self.plan_line.create(
            {"plan_id": plan.id, "sequence": 10, "command_id": command.id}
        )
        plan_log = self.server_test_1.sudo().run_flight_plan(plan, jet=self.jet_test)
        command_logs = plan_log.command_log_ids.filtered(
            lambda log: log.command_id == command
        )
        self.assertEqual(len(command_logs), 1)
        self.assertEqual(
            command_logs.command_status,
            WAYPOINT_TEMPLATE_NOT_FOUND,
            "Should finish with WAYPOINT_TEMPLATE_NOT_FOUND",
        )

    def test_create_waypoint_command_jet_busy(self):
        """
        Create a Waypoint when jet is busy (e.g. from flight plan):
        ignore_busy=True, waypoint created, log success.
        """
        self.jet_test.target_state_id = self.state_running
        command = self.Command.create(
            {
                "name": "Create waypoint jet busy",
                "action": "create_waypoint",
                "waypoint_template_id": self.waypoint_template.id,
                "fly_here": False,
            }
        )
        plan = self.Plan.create({"name": "Plan jet busy"})
        self.plan_line.create(
            {"plan_id": plan.id, "sequence": 10, "command_id": command.id}
        )
        initial_waypoint_count = len(self.jet_test.waypoint_ids)
        with mute_logger("odoo.addons.cetmix_tower_server.models.cx_tower_jet"):
            plan_log = self.server_test_1.sudo().run_flight_plan(
                plan, jet=self.jet_test
            )
        command_logs = plan_log.command_log_ids.filtered(
            lambda log: log.command_id == command
        )
        self.assertEqual(len(command_logs), 1)
        self.assertTrue(
            command_logs.finish_date,
            "Command log should be finished by waypoint callback when jet busy",
        )
        self.assertEqual(
            command_logs.command_status,
            0,
            "Create waypoint command should succeed when jet is busy "
            "(ignore_busy=True)",
        )
        self.assertEqual(
            len(self.jet_test.waypoint_ids),
            initial_waypoint_count + 1,
            "One new waypoint should be created despite jet busy",
        )
        self.jet_test.target_state_id = False

    def test_create_waypoint_command_wrong_jet_template(self):
        """Create a Waypoint with template for another jet template: False
        and WAYPOINT_CREATE_FAILED."""
        from ..models.constants import WAYPOINT_CREATE_FAILED

        other_jet_template = self.JetTemplate.create(
            {
                "name": "Other Jet Template",
                "reference": "other_jet_template_cmd",
            }
        )
        other_waypoint_template = self.JetWaypointTemplate.create(
            {
                "name": "Other Waypoint Template",
                "jet_template_id": other_jet_template.id,
            }
        )
        command = self.Command.create(
            {
                "name": "Create waypoint wrong template",
                "action": "create_waypoint",
                "waypoint_template_id": other_waypoint_template.id,
                "fly_here": False,
            }
        )
        plan = self.Plan.create({"name": "Plan wrong template"})
        self.plan_line.create(
            {"plan_id": plan.id, "sequence": 10, "command_id": command.id}
        )
        with mute_logger("odoo.addons.cetmix_tower_server.models.cx_tower_jet"):
            plan_log = self.server_test_1.sudo().run_flight_plan(
                plan, jet=self.jet_test
            )
        command_logs = plan_log.command_log_ids.filtered(
            lambda log: log.command_id == command
        )
        self.assertEqual(len(command_logs), 1)
        self.assertEqual(
            command_logs.command_status,
            WAYPOINT_CREATE_FAILED,
            "Should finish with WAYPOINT_CREATE_FAILED when template is "
            "for another jet template",
        )
        self.assertTrue(command_logs.finish_date)

    def test_create_waypoint_command_waypoint_reaches_error(self):
        """Create plan fails: waypoint goes to error, callback finishes
        command log with error."""
        from ..models.constants import WAYPOINT_CREATE_FAILED

        fail_command = self.Command.create(
            {
                "name": "Fail command",
                "action": "python_code",
                "code": "result = {'exit_code': 1, 'message': 'fail'}",
            }
        )
        fail_plan = self.Plan.create({"name": "Plan that fails"})
        self.plan_line.create(
            {
                "plan_id": fail_plan.id,
                "sequence": 10,
                "command_id": fail_command.id,
            }
        )
        waypoint_template_with_failing_plan = self.JetWaypointTemplate.create(
            {
                "name": "Waypoint template with failing create plan",
                "jet_template_id": self.jet_template_test.id,
                "plan_create_id": fail_plan.id,
            }
        )
        command = self.Command.create(
            {
                "name": "Create waypoint with failing plan",
                "action": "create_waypoint",
                "waypoint_template_id": waypoint_template_with_failing_plan.id,
                "fly_here": False,
            }
        )
        plan = self.Plan.create({"name": "Plan create waypoint error"})
        self.plan_line.create(
            {"plan_id": plan.id, "sequence": 10, "command_id": command.id}
        )
        plan_log = self.server_test_1.sudo().run_flight_plan(plan, jet=self.jet_test)
        command_logs = plan_log.command_log_ids.filtered(
            lambda log: log.command_id == command
        )
        self.assertEqual(len(command_logs), 1)
        log_record = command_logs[0]
        self.assertTrue(
            log_record.finish_date,
            "Command log should be finished by waypoint callback when "
            "waypoint reaches error",
        )
        self.assertNotEqual(
            log_record.command_status,
            0,
            "Command should finish with error status",
        )
        self.assertEqual(
            log_record.command_status,
            WAYPOINT_CREATE_FAILED,
            "Callback should use WAYPOINT_CREATE_FAILED when plan fails",
        )
        waypoints_with_log = self.jet_test.waypoint_ids.filtered(
            lambda w: w.created_from_command_log_id == log_record
        )
        self.assertEqual(len(waypoints_with_log), 1)
        self.assertEqual(
            waypoints_with_log.state,
            "error",
            "Waypoint should be in error state after create plan fails",
        )

    def test_finalize_create_waypoint_command_log_double_finish_guard(self):
        """Calling _finalize_create_waypoint_command_log twice does not
        double-finish."""
        waypoint = self.jet_test.create_waypoint(
            self.waypoint_template,
            created_from_command_log=None,
        )
        log_record = self.CommandLog.create(
            {
                "server_id": self.server_test_1.id,
                "command_id": self.Command.create(
                    {
                        "name": "Dummy create waypoint",
                        "action": "create_waypoint",
                        "waypoint_template_id": self.waypoint_template.id,
                    }
                ).id,
                "start_date": fields.Datetime.now(),
            }
        )
        waypoint.created_from_command_log_id = log_record
        self.assertFalse(log_record.finish_date, "Log should not be finished yet")
        waypoint._finalize_create_waypoint_command_log(success=True)
        self.assertTrue(log_record.finish_date, "Log should be finished once")
        finish_date_first = log_record.finish_date
        waypoint._finalize_create_waypoint_command_log(success=True)
        self.assertEqual(
            log_record.finish_date,
            finish_date_first,
            "Second call should not change finish_date (guard)",
        )
