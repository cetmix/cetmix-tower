# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

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

        # available_action_ids should be empty recordset
        self.assertEqual(
            len(self.jet_test.available_action_ids),
            1,
            "Available actions should include create action when jet has no state",
        )
        self.assertEqual(
            self.jet_test.available_action_ids,
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
            len(self.jet_test.available_action_ids),
            3,  # running_to_stopped, running_to_error, and destroy
            "Should have available actions from common setup",
        )
        expected_actions = (
            self.action_running_to_stopped
            | self.action_running_to_error
            | self.action_destroy
        )
        self.assertEqual(
            self.jet_test.available_action_ids,
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
            len(self.jet_test.available_action_ids),
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
            self.jet_test.available_action_ids,
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
            actual_actions = self.jet_test.available_action_ids
            expected_actions_set = set(expected_actions)
            actual_actions_set = set(actual_actions)

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
            self.jet_test.available_action_ids,
            expected_actions,
            "Should have all actions from running state initially",
        )

        # Change action's state_from_id (this should trigger recomputation)
        action.state_from_id = self.state_stopped

        # Jet should no longer have this specific action available
        # but should still have other actions from running state
        expected_remaining_actions = self.action_running_to_error | self.action_destroy
        self.assertEqual(
            self.jet_test.available_action_ids,
            expected_remaining_actions,
            "Should have remaining actions after changing one action's state_from_id",
        )

        # Change jet state to match action's new state_from_id
        self.jet_test.state_id = self.state_stopped

        # Now the modified action should be available again,
        # plus any other actions from stopped state
        expected_actions = action | self.action_stopped_to_running
        self.assertEqual(
            self.jet_test.available_action_ids,
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
            self.jet_odoo.available_action_ids,
            odoo_action,
            "Odoo jet should only see Odoo actions",
        )
        self.assertEqual(
            self.jet_wordpress.available_action_ids,
            wp_action,
            "WordPress jet should only see WordPress actions",
        )

        # Odoo jet should not see WordPress actions
        self.assertNotIn(
            wp_action,
            self.jet_odoo.available_action_ids,
            "Odoo jet should not see WordPress actions",
        )
        # WordPress jet should not see Odoo actions
        self.assertNotIn(
            odoo_action,
            self.jet_wordpress.available_action_ids,
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
        jet_with_different_server = self.Jet.create(
            {
                "name": "Jet With Different Server",
                "reference": "jet_with_different_server",
                "jet_template_id": self.jet_template_test.id,
                "server_id": self.server_test_1.id,
            }
        )
        domain = jet_with_different_server.jet_template_domain
        expected_domain = [("server_ids", "in", [self.server_test_1.id])]
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
