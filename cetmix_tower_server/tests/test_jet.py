# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError, ValidationError

from .common_jets import TestTowerJetsCommon


class TestTowerJet(TestTowerJetsCommon):
    """
    Test the Jet model functionality
    """

    # All jet-related test data is now inherited from TestTowerJetsCommon

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
            self.jet_test.action_available_ids,
            self.action_create,
            "Available action should be the create action",
        )

    def test_compute_available_actions_with_actions_in_template(self):
        """
        Test _compute_available_actions when template has actions
        """
        # Set jet state
        self.jet_test.state_id = self.state_running

        # Template has actions in common setup, so should have available actions
        self.assertEqual(
            len(self.jet_test.action_available_ids),
            3,  # running_to_stopped, running_to_error, and destroy
            "Should have available actions from common setup",
        )
        expected_actions = (
            self.action_running_to_stopped
            | self.action_running_to_error
            | self.action_destroy
        )
        self.assertEqual(
            self.jet_test.action_available_ids,
            expected_actions,
            "Should have all actions from running state",
        )

    def test_compute_available_actions_create_action_not_available(self):
        """
        Test _compute_available_actions when create action
        is not available (jet has state)
        """
        # Set jet state to any state
        self.jet_test.state_id = self.state_running

        # Create action should not be available (it has no state_from_id)
        # The common action_create has no state_from_id, so it won't be available
        self.assertEqual(
            len(self.jet_test.action_available_ids),
            3,  # running_to_stopped, running_to_error, and destroy
            "Create action should not be available (no state_from_id)",
        )

    def test_compute_available_actions_destroy_action(self):
        """
        Test _compute_available_actions with destroy action (no state_to_id)
        """
        # Use common destroy action from setup
        # Set jet state to running
        self.jet_test.state_id = self.state_running

        # Destroy action should be available along with other actions
        expected_actions = (
            self.action_running_to_stopped
            | self.action_running_to_error
            | self.action_destroy
        )
        self.assertEqual(
            self.jet_test.action_available_ids,
            expected_actions,
            "Should return destroy action along with other actions from running state",
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
            self.jet_test.action_available_ids,
            expected_actions,
            "Should have all actions from running state initially",
        )

        # Change action's state_from_id (this should trigger recomputation)
        action.state_from_id = self.state_stopped

        # Jet should no longer have this specific action available
        # but should still have other actions from running state
        expected_remaining_actions = self.action_running_to_error | self.action_destroy
        self.assertEqual(
            self.jet_test.action_available_ids,
            expected_remaining_actions,
            "Should have remaining actions after changing one action's state_from_id",
        )

        # Change jet state to match action's new state_from_id
        self.jet_test.state_id = self.state_stopped

        # Now the modified action should be available again,
        # plus any other actions from stopped state
        expected_actions = action | self.action_stopped_to_running
        self.assertEqual(
            self.jet_test.action_available_ids,
            expected_actions,
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
            self.jet_odoo.action_available_ids,
            odoo_action,
            "Odoo jet should only see Odoo actions",
        )
        self.assertEqual(
            self.jet_wordpress.action_available_ids,
            wp_action,
            "WordPress jet should only see WordPress actions",
        )

        # Odoo jet should not see WordPress actions
        self.assertNotIn(
            wp_action,
            self.jet_odoo.action_available_ids,
            "Odoo jet should not see WordPress actions",
        )
        # WordPress jet should not see Odoo actions
        self.assertNotIn(
            odoo_action,
            self.jet_wordpress.action_available_ids,
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

    def test_jet_requires_ids_empty_template_dependencies(self):
        """
        Test _compute_jet_requires_ids when template has no dependencies
        """
        # Create jet with tower core which has no dependencies
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
            "Jet should have no dependencies when template has none",
        )

    def test_jet_requires_ids_complex_hierarchy(self):
        """
        Test _compute_jet_requires_ids with complex dependency hierarchy
        """
        # Test WooCommerce jet which depends on both WordPress and Odoo
        woocommerce_deps = self.jet_woocommerce.jet_requires_ids

        # Should have 2 direct dependencies
        self.assertEqual(
            len(woocommerce_deps), 2, "WooCommerce should have 2 direct dependencies"
        )

        # Check that all dependencies are correctly set
        dep_templates = woocommerce_deps.mapped(
            "jet_template_dependency_id.template_required_id"
        )
        expected_templates = {self.jet_template_wordpress, self.jet_template_odoo}
        self.assertEqual(
            set(dep_templates),
            expected_templates,
            "Should depend on WordPress and Odoo",
        )

        # Verify that each dependency has correct template reference
        for dep in woocommerce_deps:
            self.assertEqual(
                dep.jet_template_dependency_id.template_id,
                self.jet_template_woocommerce_odoo,
                "Dependency should reference WooCommerce template",
            )
            self.assertIn(
                dep.jet_template_dependency_id.template_required_id,
                expected_templates,
                "Required template should be WordPress or Odoo",
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
        self.jet_test.with_user(self.user).bring_to_state("test_running")
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
        self.jet_test.with_user(self.manager).bring_to_state("test_stopped")
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
        self.jet_test.with_user(self.root).bring_to_state("test_error")
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
            self.jet_test.with_user(self.user).bring_to_state("test_stopped")

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
            self.jet_test.with_user(self.user).bring_to_state("test_error")

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
            self.jet_test.with_user(self.manager).bring_to_state("test_error")

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
        self.jet_test.with_user(self.manager).bring_to_state("test_running")
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
        self.jet_test.with_user(self.manager).bring_to_state("test_running")
        self.assertEqual(
            self.jet_test.state_id,
            self.state_running,
            "Manager not in manager_ids should be able to access user-level state",
        )

    def test_bring_to_state_manager_not_in_manager_ids_cannot_access_manager_level(
        self
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
            self.jet_test.with_user(self.manager).bring_to_state("test_stopped")

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
        self.jet_test.with_user(self.root).bring_to_state("test_stopped")
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
            self.jet_test.bring_to_state("invalid_state_reference")

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
