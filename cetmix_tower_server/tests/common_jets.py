# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from .common import TestTowerCommon


class TestTowerJetsCommon(TestTowerCommon):
    """
    Common test class for Jet and JetTemplate models with shared test data
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create jet states for testing
        cls.state_initial = cls.JetState.create(
            {
                "name": "Initial",
                "reference": "initial",
                "sequence": 10,
                "color": 1,
            }
        )
        cls.state_running = cls.JetState.create(
            {
                "name": "Running",
                "reference": "running",
                "sequence": 20,
                "color": 2,
            }
        )
        cls.state_stopped = cls.JetState.create(
            {
                "name": "Stopped",
                "reference": "stopped",
                "sequence": 30,
                "color": 3,
            }
        )
        cls.state_error = cls.JetState.create(
            {
                "name": "Error",
                "reference": "error",
                "sequence": 40,
                "color": 4,
            }
        )

        # Create transit states
        cls.state_starting = cls.JetState.create(
            {
                "name": "Starting",
                "reference": "starting",
                "sequence": 15,
                "color": 5,
            }
        )
        cls.state_stopping = cls.JetState.create(
            {
                "name": "Stopping",
                "reference": "stopping",
                "sequence": 25,
                "color": 6,
            }
        )

        # Create test states for pathfinding and adjacency tests
        cls.state_a = cls.JetState.create(
            {
                "name": "State A",
                "reference": "state_a",
                "sequence": 30,
            }
        )
        cls.state_b = cls.JetState.create(
            {
                "name": "State B",
                "reference": "state_b",
                "sequence": 31,
            }
        )
        cls.state_c = cls.JetState.create(
            {
                "name": "State C",
                "reference": "state_c",
                "sequence": 32,
            }
        )
        cls.state_d = cls.JetState.create(
            {
                "name": "State D",
                "reference": "state_d",
                "sequence": 33,
            }
        )

        # Create jet template for testing
        cls.jet_template_test = cls.JetTemplate.create(
            {
                "name": "Test Jet Template",
                "reference": "test_jet_template",
                "server_ids": [(4, cls.server_test_1.id)],
            }
        )

        # Create dependency hierarchy for testing:
        # Odoo -> Postgres, Nginx -> Docker -> Tower Core
        # Level 1: Base dependencies
        cls.jet_template_tower_core = cls.JetTemplate.create(
            {
                "name": "Tower Core",
                "reference": "tower_core",
                "server_ids": [(4, cls.server_test_1.id)],
            }
        )

        # Level 2: Infrastructure
        cls.jet_template_docker = cls.JetTemplate.create(
            {
                "name": "Docker",
                "reference": "docker",
                "server_ids": [(4, cls.server_test_1.id)],
            }
        )
        # Docker requires Tower Core to be running
        cls.JetTemplateDependency.create(
            {
                "template_id": cls.jet_template_docker.id,
                "template_required_id": cls.jet_template_tower_core.id,
                "state_required_id": cls.state_running.id,
            }
        )

        # Level 3: Services
        cls.jet_template_nginx = cls.JetTemplate.create(
            {
                "name": "Nginx",
                "reference": "nginx",
                "server_ids": [(4, cls.server_test_1.id)],
            }
        )
        # Nginx requires Docker to be running
        cls.JetTemplateDependency.create(
            {
                "template_id": cls.jet_template_nginx.id,
                "template_required_id": cls.jet_template_docker.id,
                "state_required_id": cls.state_running.id,
            }
        )

        # Level 3: Database
        cls.jet_template_postgres = cls.JetTemplate.create(
            {
                "name": "Postgres",
                "reference": "postgres",
                "server_ids": [(4, cls.server_test_1.id)],
            }
        )
        # Postgres requires Docker to be running
        cls.JetTemplateDependency.create(
            {
                "template_id": cls.jet_template_postgres.id,
                "template_required_id": cls.jet_template_docker.id,
                "state_required_id": cls.state_running.id,
            }
        )

        cls.jet_template_mariadb = cls.JetTemplate.create(
            {
                "name": "MariaDB",
                "reference": "mariadb",
                "server_ids": [(4, cls.server_test_1.id)],
            }
        )
        # MariaDB requires Docker to be running
        cls.JetTemplateDependency.create(
            {
                "template_id": cls.jet_template_mariadb.id,
                "template_required_id": cls.jet_template_docker.id,
                "state_required_id": cls.state_running.id,
            }
        )

        # Level 5: Applications
        cls.jet_template_odoo = cls.JetTemplate.create(
            {
                "name": "Odoo",
                "reference": "odoo",
                "server_ids": [(4, cls.server_test_1.id)],
            }
        )
        # Odoo requires Postgres to be running
        cls.JetTemplateDependency.create(
            {
                "template_id": cls.jet_template_odoo.id,
                "template_required_id": cls.jet_template_postgres.id,
                "state_required_id": cls.state_running.id,
            }
        )
        # Odoo requires Nginx to be running
        cls.JetTemplateDependency.create(
            {
                "template_id": cls.jet_template_odoo.id,
                "template_required_id": cls.jet_template_nginx.id,
                "state_required_id": cls.state_running.id,
            }
        )

        cls.jet_template_wordpress = cls.JetTemplate.create(
            {
                "name": "WordPress",
                "reference": "wordpress",
                "server_ids": [(4, cls.server_test_1.id)],
            }
        )
        # WordPress requires MariaDB to be running
        cls.JetTemplateDependency.create(
            {
                "template_id": cls.jet_template_wordpress.id,
                "template_required_id": cls.jet_template_mariadb.id,
                "state_required_id": cls.state_running.id,
            }
        )
        # WordPress requires Nginx to be running
        cls.JetTemplateDependency.create(
            {
                "template_id": cls.jet_template_wordpress.id,
                "template_required_id": cls.jet_template_nginx.id,
                "state_required_id": cls.state_running.id,
            }
        )

        # Level 6: E-commerce Integration
        cls.jet_template_woocommerce_odoo = cls.JetTemplate.create(
            {
                "name": "WooCommerce with Odoo",
                "reference": "woocommerce_odoo",
                "server_ids": [(4, cls.server_test_1.id)],
            }
        )
        # WooCommerce requires WordPress to be running
        cls.JetTemplateDependency.create(
            {
                "template_id": cls.jet_template_woocommerce_odoo.id,
                "template_required_id": cls.jet_template_wordpress.id,
                "state_required_id": cls.state_running.id,
            }
        )
        # WooCommerce requires Odoo to be running
        cls.JetTemplateDependency.create(
            {
                "template_id": cls.jet_template_woocommerce_odoo.id,
                "template_required_id": cls.jet_template_odoo.id,
                "state_required_id": cls.state_running.id,
            }
        )

        # Create test jets for different templates
        cls.jet_test = cls.Jet.create(
            {
                "name": "Test Jet",
                "reference": "test_jet",
                "jet_template_id": cls.jet_template_test.id,
                "server_id": cls.server_test_1.id,
            }
        )

        cls.jet_odoo = cls.Jet.create(
            {
                "name": "Odoo Jet",
                "reference": "odoo_jet",
                "jet_template_id": cls.jet_template_odoo.id,
                "server_id": cls.server_test_1.id,
            }
        )

        cls.jet_wordpress = cls.Jet.create(
            {
                "name": "WordPress Jet",
                "reference": "wordpress_jet",
                "jet_template_id": cls.jet_template_wordpress.id,
                "server_id": cls.server_test_1.id,
            }
        )

        cls.jet_woocommerce = cls.Jet.create(
            {
                "name": "WooCommerce Jet",
                "reference": "woocommerce_jet",
                "jet_template_id": cls.jet_template_woocommerce_odoo.id,
                "server_id": cls.server_test_1.id,
            }
        )

        # Add some dependencies with different state requirements for testing
        # Create a monitoring template that requires services to be in "running" state
        cls.jet_template_monitoring = cls.JetTemplate.create(
            {
                "name": "Monitoring",
                "reference": "monitoring",
                "server_ids": [(4, cls.server_test_1.id)],
            }
        )

        # Monitoring requires Odoo to be running (for business metrics)
        cls.JetTemplateDependency.create(
            {
                "template_id": cls.jet_template_monitoring.id,
                "template_required_id": cls.jet_template_odoo.id,
                "state_required_id": cls.state_running.id,
            }
        )

        # Create a backup template that requires services to be in "stopped" state
        cls.jet_template_backup = cls.JetTemplate.create(
            {
                "name": "Backup",
                "reference": "backup",
                "server_ids": [(4, cls.server_test_1.id)],
            }
        )

        # Backup requires Postgres to be stopped for safe backup
        cls.JetTemplateDependency.create(
            {
                "template_id": cls.jet_template_backup.id,
                "template_required_id": cls.jet_template_postgres.id,
                "state_required_id": cls.state_stopped.id,
            }
        )

        # Create common actions for testing
        cls.action_running_to_stopped = cls.JetAction.create(
            {
                "name": "Stop Action",
                "reference": "stop_action",
                "jet_template_id": cls.jet_template_test.id,
                "state_from_id": cls.state_running.id,
                "state_to_id": cls.state_stopped.id,
                "state_transit_id": cls.state_stopping.id,
                "priority": 10,
            }
        )

        cls.action_stopped_to_running = cls.JetAction.create(
            {
                "name": "Start Action",
                "reference": "start_action",
                "jet_template_id": cls.jet_template_test.id,
                "state_from_id": cls.state_stopped.id,
                "state_to_id": cls.state_running.id,
                "state_transit_id": cls.state_starting.id,
                "priority": 10,
            }
        )

        cls.action_running_to_error = cls.JetAction.create(
            {
                "name": "Error Action",
                "reference": "error_action",
                "jet_template_id": cls.jet_template_test.id,
                "state_from_id": cls.state_running.id,
                "state_to_id": cls.state_error.id,
                "state_transit_id": cls.state_error.id,
                "priority": 20,
            }
        )

        cls.action_error_to_running = cls.JetAction.create(
            {
                "name": "Recover Action",
                "reference": "recover_action",
                "jet_template_id": cls.jet_template_test.id,
                "state_from_id": cls.state_error.id,
                "state_to_id": cls.state_running.id,
                "state_transit_id": cls.state_starting.id,
                "priority": 10,
            }
        )

        cls.action_initial_to_running = cls.JetAction.create(
            {
                "name": "Initialize Action",
                "reference": "initialize_action",
                "jet_template_id": cls.jet_template_test.id,
                "state_from_id": cls.state_initial.id,
                "state_to_id": cls.state_running.id,
                "state_transit_id": cls.state_starting.id,
                "priority": 5,
            }
        )

        # Create actions for pathfinding tests (A -> B -> C -> D)
        cls.action_a_to_b = cls.JetAction.create(
            {
                "name": "Action A to B",
                "reference": "action_a_to_b",
                "jet_template_id": cls.jet_template_test.id,
                "state_from_id": cls.state_a.id,
                "state_to_id": cls.state_b.id,
                "state_transit_id": cls.state_starting.id,
                "priority": 10,
            }
        )

        cls.action_b_to_c = cls.JetAction.create(
            {
                "name": "Action B to C",
                "reference": "action_b_to_c",
                "jet_template_id": cls.jet_template_test.id,
                "state_from_id": cls.state_b.id,
                "state_to_id": cls.state_c.id,
                "state_transit_id": cls.state_stopping.id,
                "priority": 10,
            }
        )

        cls.action_c_to_d = cls.JetAction.create(
            {
                "name": "Action C to D",
                "reference": "action_c_to_d",
                "jet_template_id": cls.jet_template_test.id,
                "state_from_id": cls.state_c.id,
                "state_to_id": cls.state_d.id,
                "state_transit_id": cls.state_stopping.id,
                "priority": 10,
            }
        )

        cls.action_a_to_c = cls.JetAction.create(
            {
                "name": "Action A to C (direct)",
                "reference": "action_a_to_c",
                "jet_template_id": cls.jet_template_test.id,
                "state_from_id": cls.state_a.id,
                "state_to_id": cls.state_c.id,
                "state_transit_id": cls.state_stopping.id,
                "priority": 10,
            }
        )

        # Create border actions (create and destroy)
        cls.action_create = cls.JetAction.create(
            {
                "name": "Create Action",
                "reference": "create_action",
                "jet_template_id": cls.jet_template_test.id,
                "state_from_id": False,  # No initial state
                "state_to_id": cls.state_running.id,
                "state_transit_id": cls.state_starting.id,
                "priority": 1,
            }
        )

        cls.action_destroy = cls.JetAction.create(
            {
                "name": "Destroy Action",
                "reference": "destroy_action",
                "jet_template_id": cls.jet_template_test.id,
                "state_from_id": cls.state_running.id,
                "state_to_id": False,  # No final state
                "state_transit_id": cls.state_stopping.id,
                "priority": 1,
            }
        )
