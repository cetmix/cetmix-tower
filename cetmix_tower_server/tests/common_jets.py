# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError
from odoo.tools import LazyTranslate

from .common import TestTowerCommon

_lt = LazyTranslate(__name__, default_lang="en_US")


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
                "name": "Test Initial",
                "reference": "test_initial",
                "sequence": 10,
                "color": 1,
            }
        )
        cls.state_running = cls.JetState.create(
            {
                "name": "Test Running",
                "reference": "test_running",
                "sequence": 20,
                "color": 2,
            }
        )
        cls.state_stopped = cls.JetState.create(
            {
                "name": "Test Stopped",
                "reference": "test_stopped",
                "sequence": 30,
                "color": 3,
            }
        )
        cls.state_error = cls.JetState.create(
            {
                "name": "Test Error",
                "reference": "test_error",
                "sequence": 40,
                "color": 4,
            }
        )

        # Create transit states
        cls.state_starting = cls.JetState.create(
            {
                "name": "Test Starting",
                "reference": "test_starting",
                "sequence": 15,
                "color": 5,
            }
        )
        cls.state_stopping = cls.JetState.create(
            {
                "name": "Test Stopping",
                "reference": "test_stopping",
                "sequence": 25,
                "color": 6,
            }
        )

        # Create test states for pathfinding and adjacency tests
        cls.state_a = cls.JetState.create(
            {
                "name": "Test State A",
                "reference": "test_state_a",
                "sequence": 30,
            }
        )
        cls.state_b = cls.JetState.create(
            {
                "name": "Test State B",
                "reference": "test_state_b",
                "sequence": 31,
            }
        )
        cls.state_c = cls.JetState.create(
            {
                "name": "Test State C",
                "reference": "test_state_c",
                "sequence": 32,
            }
        )
        cls.state_d = cls.JetState.create(
            {
                "name": "Test State D",
                "reference": "test_state_d",
                "sequence": 33,
            }
        )

        # Create jet template for testing
        cls.jet_template_test = cls.JetTemplate.create(
            {
                "name": "Test Jet Template",
                "reference": "test_jet_template",
            }
        )

        # Create dependency hierarchy for testing:
        # Odoo -> Postgres, Nginx -> Docker -> Tower Core
        # Level 1: Base dependencies
        cls.jet_template_tower_core = cls.JetTemplate.create(
            {
                "name": "Tower Core",
                "reference": "tower_core",
            }
        )

        # Level 2: Infrastructure
        cls.jet_template_docker = cls.JetTemplate.create(
            {
                "name": "Docker",
                "reference": "docker",
            }
        )
        # Docker requires Tower Core to be running
        cls._create_jet_template_dependency(
            template=cls.jet_template_docker,
            template_required=cls.jet_template_tower_core,
            state_required_id=cls.state_running.id,
        )

        # Level 3: Services
        cls.jet_template_nginx = cls.JetTemplate.create(
            {
                "name": "Nginx",
                "reference": "nginx",
            }
        )
        # Nginx requires Docker to be running
        cls._create_jet_template_dependency(
            template=cls.jet_template_nginx,
            template_required=cls.jet_template_docker,
            state_required_id=cls.state_running.id,
        )

        # Level 3: Database
        cls.jet_template_postgres = cls.JetTemplate.create(
            {
                "name": "Postgres",
                "reference": "postgres",
            }
        )
        # Postgres requires Docker to be running
        cls._create_jet_template_dependency(
            template=cls.jet_template_postgres,
            template_required=cls.jet_template_docker,
            state_required_id=cls.state_running.id,
        )

        cls.jet_template_mariadb = cls.JetTemplate.create(
            {
                "name": "MariaDB",
                "reference": "mariadb",
            }
        )
        # MariaDB requires Docker to be running
        cls._create_jet_template_dependency(
            template=cls.jet_template_mariadb,
            template_required=cls.jet_template_docker,
            state_required_id=cls.state_running.id,
        )

        # Level 5: Applications
        cls.jet_template_odoo = cls.JetTemplate.create(
            {
                "name": "Odoo",
                "reference": "odoo",
            }
        )
        # Odoo requires Postgres to be running
        cls._create_jet_template_dependency(
            template=cls.jet_template_odoo,
            template_required=cls.jet_template_postgres,
            state_required_id=cls.state_running.id,
        )
        # Odoo requires Nginx to be running
        cls._create_jet_template_dependency(
            template=cls.jet_template_odoo,
            template_required=cls.jet_template_nginx,
            state_required_id=cls.state_running.id,
        )

        cls.jet_template_wordpress = cls.JetTemplate.create(
            {
                "name": "WordPress",
                "reference": "wordpress",
            }
        )
        # WordPress requires MariaDB to be running
        cls._create_jet_template_dependency(
            template=cls.jet_template_wordpress,
            template_required=cls.jet_template_mariadb,
            state_required_id=cls.state_running.id,
        )
        # WordPress requires Nginx to be running
        cls._create_jet_template_dependency(
            template=cls.jet_template_wordpress,
            template_required=cls.jet_template_nginx,
            state_required_id=cls.state_running.id,
        )

        # Level 6: E-commerce Integration
        cls.jet_template_woocommerce_odoo = cls.JetTemplate.create(
            {
                "name": "WooCommerce with Odoo",
                "reference": "woocommerce_odoo",
            }
        )
        # WooCommerce requires WordPress to be running
        cls._create_jet_template_dependency(
            template=cls.jet_template_woocommerce_odoo,
            template_required=cls.jet_template_wordpress,
            state_required_id=cls.state_running.id,
        )
        # WooCommerce requires Odoo to be running
        cls._create_jet_template_dependency(
            template=cls.jet_template_woocommerce_odoo,
            template_required=cls.jet_template_odoo,
            state_required_id=cls.state_running.id,
        )

        # Create test jets for different templates
        cls.jet_test = cls._create_jet(
            name="Test Jet",
            reference="test_jet",
            template=cls.jet_template_test,
            server=cls.server_test_1,
        )

        cls.jet_odoo = cls._create_jet(
            name="Odoo Jet",
            reference="odoo_jet",
            template=cls.jet_template_odoo,
            server=cls.server_test_1,
        )

        cls.jet_wordpress = cls._create_jet(
            name="WordPress Jet",
            reference="wordpress_jet",
            template=cls.jet_template_wordpress,
            server=cls.server_test_1,
        )

        cls.jet_woocommerce = cls._create_jet(
            name="WooCommerce Jet",
            reference="woocommerce_jet",
            template=cls.jet_template_woocommerce_odoo,
            server=cls.server_test_1,
        )

        # Add some dependencies with different state requirements for testing
        # Create a monitoring template that requires services to be in "running" state
        cls.jet_template_monitoring = cls.JetTemplate.create(
            {
                "name": "Monitoring",
                "reference": "monitoring",
            }
        )

        # Monitoring requires Odoo to be running (for business metrics)
        cls._create_jet_template_dependency(
            template=cls.jet_template_monitoring,
            template_required=cls.jet_template_odoo,
            state_required_id=cls.state_running.id,
        )

        # Create a backup template that requires services to be in "stopped" state
        cls.jet_template_backup = cls.JetTemplate.create(
            {
                "name": "Backup",
                "reference": "backup",
            }
        )

        # Backup requires Postgres to be stopped for safe backup
        cls._create_jet_template_dependency(
            template=cls.jet_template_backup,
            template_required=cls.jet_template_postgres,
            state_required_id=cls.state_stopped.id,
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

        # Create a clean template for tests that need isolation from common actions
        cls.clean_template = cls.JetTemplate.create(
            {
                "name": "Clean Template",
                "reference": "clean_template",
            }
        )

        # Create waypoint template for testing
        cls.waypoint_template = cls.env["cx.tower.jet.waypoint.template"].create(
            {
                "name": "Test Waypoint Template",
                "jet_template_id": cls.jet_template_test.id,
            }
        )
        cls.waypoint_template_2 = cls.env["cx.tower.jet.waypoint.template"].create(
            {
                "name": "Test Waypoint Template 2",
                "jet_template_id": cls.jet_template_test.id,
            }
        )

        # Create waypoint for testing
        cls.waypoint = cls.env["cx.tower.jet.waypoint"].create(
            {
                "name": "Test Waypoint",
                "jet_id": cls.jet_test.id,
                "waypoint_template_id": cls.waypoint_template.id,
            }
        )

        # Model references reused by helpers
        cls.JetDependency = cls.env["cx.tower.jet.dependency"]
        cls.JetWaypointTemplate = cls.env["cx.tower.jet.waypoint.template"]
        cls.JetWaypoint = cls.env["cx.tower.jet.waypoint"]

    @classmethod
    def _create_jet(
        cls,
        name,
        reference,
        template=None,
        server=None,
        user_ids=None,
        manager_ids=None,
        server_user_ids=None,
        server_manager_ids=None,
        with_user=None,
    ):
        """
        Helper method to create a jet
        with specified access configuration

        Args:
            name (str): Name of the jet
            reference (str): Reference of the jet
            template (cx.tower.jet.template): Template for the jet
            (if None, defaults to jet_template_test)
            server (cx.tower.server): Server for the jet
            (if None, defaults to server_test_1)
            user_ids (list): List of user IDs for the jet
            manager_ids (list): List of manager IDs for the jet
            server_user_ids (list): List of user IDs for the server
            server_manager_ids (list): List of manager IDs for the server
            with_user (res.users): Optional user
                to create the jet as (for access rule testing)

        Returns:
            cx.tower.jet: Created jet record
        """
        if template is None:
            template = cls.jet_template_test
        if server is None:
            server = cls.server_test_1

        # Configure server access
        if server_user_ids is not None or server_manager_ids is not None:
            server.write(
                {
                    "user_ids": server_user_ids
                    if server_user_ids is not None
                    else [(5, 0, 0)],
                    "manager_ids": server_manager_ids
                    if server_manager_ids is not None
                    else [(5, 0, 0)],
                }
            )

        # Create jet with access configuration
        jet_vals = {
            "name": name,
            "reference": reference,
            "jet_template_id": template.id,
            "server_id": server.id,
            "user_ids": user_ids if user_ids is not None else [(5, 0, 0)],
            "manager_ids": manager_ids if manager_ids is not None else [(5, 0, 0)],
        }
        jet_model = cls.Jet.with_user(with_user) if with_user else cls.Jet
        jet = jet_model.create(jet_vals)
        return jet

    @classmethod
    def _create_jet_dependency(
        cls,
        jet_name,
        jet_reference,
        depends_on_name,
        depends_on_reference,
        jet_user_ids=None,
        jet_manager_ids=None,
        depends_on_user_ids=None,
        depends_on_manager_ids=None,
        jet_server_user_ids=None,
        jet_server_manager_ids=None,
        depends_on_server_user_ids=None,
        depends_on_server_manager_ids=None,
        with_user=None,
        jet_template=None,
        depends_on_template=None,
    ):
        """Helper method to create a dependency between two jets

        Args:
            jet_name (str): Name of the main jet
            jet_reference (str): Reference of the main jet
            depends_on_name (str): Name of the jet this depends on
            depends_on_reference (str): Reference of the jet this depends on
            jet_user_ids (list): User IDs for the main jet
            jet_manager_ids (list): Manager IDs for the main jet
            depends_on_user_ids (list): User IDs for the depends_on jet
            depends_on_manager_ids (list): Manager IDs for the depends_on jet
            jet_server_user_ids (list): User IDs for the main jet's server
            jet_server_manager_ids (list): Manager IDs for the main jet's server
            depends_on_server_user_ids (list): User IDs for the depends_on jet's server
            depends_on_server_manager_ids (list): Manager IDs for the depends_on
                jet's server (if None, defaults to server_test_1)
            with_user (res.users): Optional user to create the dependency as
                (for access rule testing)
            jet_template: Optional template for the main jet
                (if None, defaults to jet_template_test)
            depends_on_template: Optional template for the depends_on jet
                (if None, defaults to jet_template_tower_core)

        Returns:
            tuple: (jet, depends_on_jet, dependency)
        """

        # Use different templates to avoid self-dependency error
        # Default to jet_template_test for the main jet and
        # jet_template_tower_core for depends_on
        jet_template = jet_template or cls.jet_template_test
        depends_on_template = depends_on_template or cls.jet_template_tower_core

        # Check if template dependency already exists, if so reuse it
        template_dep = cls.JetTemplateDependency.search(
            [
                ("template_id", "=", jet_template.id),
                ("template_required_id", "=", depends_on_template.id),
            ],
            limit=1,
        )
        if not template_dep:
            # Create template dependency first
            # to ensure templates are different
            (
                _template,
                _required_template,
                template_dep,
            ) = cls._create_jet_template_dependency(
                template=jet_template,
                template_required=depends_on_template,
            )

        # Create first jet
        # (always create as root to ensure proper setup)
        jet = cls._create_jet(
            jet_name,
            jet_reference,
            template=jet_template,
            user_ids=jet_user_ids,
            manager_ids=jet_manager_ids,
            server_user_ids=jet_server_user_ids,
            server_manager_ids=jet_server_manager_ids,
            with_user=None,  # Create as root to ensure proper setup
        )

        # Create second jet (depended on)
        # (also create as root to ensure proper setup)
        depends_on_jet = cls._create_jet(
            depends_on_name,
            depends_on_reference,
            template=depends_on_template,
            user_ids=depends_on_user_ids,
            manager_ids=depends_on_manager_ids,
            server_user_ids=depends_on_server_user_ids,
            server_manager_ids=depends_on_server_manager_ids,
            with_user=None,  # Create as root to ensure proper setup,
        )

        # If creating dependency with a user context, verify access first
        if with_user:
            # Verify manager can access both jets by searching in their context
            # This ensures the access rule domain can evaluate correctly
            # when creating the dependency
            jet_search = cls.Jet.with_user(with_user).search([("id", "=", jet.id)])
            depends_search = cls.Jet.with_user(with_user).search(
                [("id", "=", depends_on_jet.id)]
            )

            if not jet_search or not depends_search:
                raise AccessError(
                    _lt("Manager must have access to both jets before creating")
                )
            # Force cache refresh to ensure Many2one relations are accessible,
            jet.invalidate_recordset(["manager_ids", "user_ids"])
            depends_on_jet.invalidate_recordset(["user_ids", "manager_ids"])

        # Create dependency
        dependency_vals = {
            "jet_id": jet.id,
            "jet_depends_on_id": depends_on_jet.id,
            "jet_template_dependency_id": template_dep.id,
        }
        dependency_model = (
            cls.JetDependency.with_user(with_user) if with_user else cls.JetDependency
        )
        dependency = dependency_model.create(dependency_vals)

        return jet, depends_on_jet, dependency

    @classmethod
    def _create_jet_template_dependency(
        cls,
        template_name=None,
        template_reference=None,
        access_level="2",
        user_ids=None,
        manager_ids=None,
        template=None,
        template_required=None,
        state_required_id=None,
        with_user=None,
    ):
        """Helper method to create a dependency between two templates

        Args:
            template_name (str, optional): Name of the template (if creating new)
            template_reference (str, optional): Reference of the template
                (if creating new)
            access_level (str): Access level for the template
                (if creating new, defaults to "2")
            user_ids (list): List of user IDs for the template
            manager_ids (list): List of manager IDs for the template
            template: Existing template record or None to create new
                (if None, defaults to jet_template_test)
            template_required: Existing required template record or None to create new
                (if None, defaults to jet_template_tower_core)
            state_required_id: Optional state required ID for the dependency

        Returns:
            tuple: (template, required_template, dependency)
        """
        # Create or use existing template
        if template is None:
            template_vals = {
                "name": template_name,
                "reference": template_reference,
                "access_level": access_level,
                "user_ids": user_ids if user_ids is not None else [(5, 0, 0)],
                "manager_ids": manager_ids if manager_ids is not None else [(5, 0, 0)],
            }
            template = cls.JetTemplate.create(template_vals)

        # Create or use existing required template
        if template_required is None:
            required_template = cls.JetTemplate.create(
                {
                    "name": "Required Template",
                    "reference": "required_template",
                    "access_level": "2",
                }
            )
        else:
            required_template = template_required

        # Create dependency
        dependency_vals = {
            "template_id": template.id if hasattr(template, "id") else template,
            "template_required_id": required_template.id
            if hasattr(required_template, "id")
            else required_template,
            "state_required_id": state_required_id
            if state_required_id is not None
            else cls.state_running.id,
        }
        dependency_model = (
            cls.JetTemplateDependency.with_user(with_user)
            if with_user
            else cls.JetTemplateDependency
        )
        dependency = dependency_model.create(dependency_vals)

        return template, required_template, dependency
