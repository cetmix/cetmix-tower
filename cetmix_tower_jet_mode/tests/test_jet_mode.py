# Copyright Cetmix OU
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo.tests.common import TransactionCase


class TestJetMode(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create server (required for Jet creation)
        cls.server = cls.env["cx.tower.server"].create(
            {
                "name": "Demo Server",
                "reference": "demo_server",
                "ssh_username": "root",
                "ip_v4_address": "127.0.0.1",
            }
        )

        # Create variables
        cls.var1 = cls.env["cx.tower.variable"].create(
            {
                "name": "db_port",
                "reference": "db_port",
            }
        )
        cls.var2 = cls.env["cx.tower.variable"].create(
            {
                "name": "sys_max_users",
                "reference": "sys_max_users",
            }
        )

        # Create flight plans
        cls.plan_backup = cls.env["cx.tower.plan"].create(
            {
                "name": "Database Backup",
                "reference": "db_backup",
            }
        )
        cls.plan_upgrade = cls.env["cx.tower.plan"].create(
            {
                "name": "System Upgrade",
                "reference": "sys_upgrade",
            }
        )

        # Create Jet Template
        cls.template = cls.env["cx.tower.jet.template"].create(
            {
                "name": "Odoo Standard Template",
                "reference": "odoo_standard_template",
            }
        )

        # Link variable values to the template
        cls.val1 = cls.env["cx.tower.variable.value"].create(
            {
                "jet_template_id": cls.template.id,
                "variable_id": cls.var1.id,
                "value_char": "5432",
            }
        )
        cls.val2 = cls.env["cx.tower.variable.value"].create(
            {
                "jet_template_id": cls.template.id,
                "variable_id": cls.var2.id,
                "value_char": "100",
            }
        )

        # Create transit state (required by action)
        cls.state_transit = cls.env["cx.tower.jet.state"].create(
            {
                "name": "Processing",
                "reference": "processing",
            }
        )

        # Create template actions
        cls.act1 = cls.env["cx.tower.jet.action"].create(
            {
                "name": "Run Backup",
                "jet_template_id": cls.template.id,
                "plan_id": cls.plan_backup.id,
                "state_transit_id": cls.state_transit.id,
            }
        )
        cls.act2 = cls.env["cx.tower.jet.action"].create(
            {
                "name": "Run Upgrade",
                "jet_template_id": cls.template.id,
                "plan_id": cls.plan_upgrade.id,
                "state_transit_id": cls.state_transit.id,
            }
        )

        # Create modes on template
        cls.mode_db = cls.env["cx.tower.jet.mode"].create(
            {
                "name": "DB Only",
                "description": "<p>Test DB Mode Description</p>",
                "access_level": "2",
                "jet_template_id": cls.template.id,
                "variable_ids": [(6, 0, cls.var1.ids)],
                "action_ids": [(6, 0, cls.act1.ids)],
            }
        )

    def test_allowed_variables(self):
        """Test that allowed_variable_ids compute correctly restricts available variables"""  # noqa: E501
        self.assertEqual(
            self.mode_db.allowed_variable_ids.ids, [self.var1.id, self.var2.id]
        )
        self.assertEqual(self.mode_db.access_level, "2")

    def test_template_filtering(self):
        """Test that is_mode_allowed filters correctly based on mode on template"""
        # Initially, no active mode
        self.assertFalse(self.template.active_mode_id)
        self.assertFalse(self.template.active_mode_description)

        # Set active mode to DB Only
        self.template.active_mode_id = self.mode_db.id

        # Check related description field
        self.assertEqual(
            self.template.active_mode_description, "<p>Test DB Mode Description</p>"
        )

        # val1 is linked to var1 which is in mode_db => allowed
        self.assertTrue(self.val1.is_mode_allowed)
        # val2 is linked to var2 which is NOT in mode_db => not allowed
        self.assertFalse(self.val2.is_mode_allowed)
        # act1 is in mode_db => allowed
        self.assertTrue(self.act1.is_mode_allowed)
        # act2 is NOT in mode_db => not allowed
        self.assertFalse(self.act2.is_mode_allowed)

    def test_jet_filtering(self):
        """Test that jet variables and actions are filtered correctly based on active mode"""  # noqa: E501
        # Create Jet
        jet = self.env["cx.tower.jet"].create(
            {
                "name": "Odoo Jet instance",
                "jet_template_id": self.template.id,
                "server_id": self.server.id,
            }
        )

        # No active mode initially
        self.assertFalse(jet.active_mode_id)
        self.assertFalse(jet.active_mode_description)

        # Set active mode on Jet
        jet.active_mode_id = self.mode_db.id

        # Check related description field
        self.assertEqual(jet.active_mode_description, "<p>Test DB Mode Description</p>")

        # Create variable value for this jet and check is_mode_allowed
        val_jet_var1 = self.env["cx.tower.variable.value"].create(
            {
                "jet_id": jet.id,
                "variable_id": self.var1.id,
                "value_char": "5432",
            }
        )
        val_jet_var2 = self.env["cx.tower.variable.value"].create(
            {
                "jet_id": jet.id,
                "variable_id": self.var2.id,
                "value_char": "100",
            }
        )
        # var1 is in mode_db => allowed
        self.assertTrue(val_jet_var1.is_mode_allowed)
        # var2 is NOT in mode_db => not allowed
        self.assertFalse(val_jet_var2.is_mode_allowed)

        # Without active mode, both should be allowed
        jet.active_mode_id = False
        self.assertTrue(val_jet_var1.is_mode_allowed)
        self.assertTrue(val_jet_var2.is_mode_allowed)

        # Verify action available computation is filtered
        state_from = self.env["cx.tower.jet.state"].create({"name": "Draft"})
        jet.state_id = state_from.id
        self.act1.state_from_id = state_from.id
        self.act2.state_from_id = state_from.id

        # Force recompute
        jet._compute_available_actions()

        # Without active mode, both should be available
        jet.active_mode_id = False
        jet._compute_available_actions()
        self.assertIn(self.act1, jet.action_available_ids)
        self.assertIn(self.act2, jet.action_available_ids)

        # With DB Only mode, only backup plan should be available
        jet.active_mode_id = self.mode_db.id
        jet._compute_available_actions()
        self.assertIn(self.act1, jet.action_available_ids)
        self.assertNotIn(self.act2, jet.action_available_ids)

    def test_web_search_read_filtering(self):
        """Test that web_search_read correctly filters variable values and actions based on the active mode"""  # noqa: E501
        # Set active mode to DB Only on the template
        self.template.active_mode_id = self.mode_db.id

        # Search variable values for the template via web_search_read
        var_values = self.env["cx.tower.variable.value"].web_search_read(
            domain=[("jet_template_id", "=", self.template.id)],
            specification={"id": {}},
        )
        var_value_ids = [res["id"] for res in var_values["records"]]
        self.assertIn(self.val1.id, var_value_ids)
        self.assertNotIn(self.val2.id, var_value_ids)

        # Search actions for the template via web_search_read
        actions = self.env["cx.tower.jet.action"].web_search_read(
            domain=[("jet_template_id", "=", self.template.id)],
            specification={"id": {}},
        )
        action_ids = [res["id"] for res in actions["records"]]
        self.assertIn(self.act1.id, action_ids)
        self.assertNotIn(self.act2.id, action_ids)

        # Clear the active mode
        self.template.active_mode_id = False
        var_values = self.env["cx.tower.variable.value"].web_search_read(
            domain=[("jet_template_id", "=", self.template.id)],
            specification={"id": {}},
        )
        var_value_ids = [res["id"] for res in var_values["records"]]
        self.assertIn(self.val1.id, var_value_ids)
        self.assertIn(self.val2.id, var_value_ids)

        # Also test on a Jet instance
        jet = self.env["cx.tower.jet"].create(
            {
                "name": "Odoo Jet instance 2",
                "jet_template_id": self.template.id,
                "server_id": self.server.id,
            }
        )
        # Create a variable value for this specific jet
        val_jet = self.env["cx.tower.variable.value"].create(
            {
                "jet_id": jet.id,
                "variable_id": self.var2.id,
                "value_char": "200",
            }
        )
        # Active mode is DB Only (only self.var1 allowed)
        jet.active_mode_id = self.mode_db.id

        var_values = self.env["cx.tower.variable.value"].web_search_read(
            domain=[("jet_id", "=", jet.id)], specification={"id": {}}
        )
        var_value_ids = [res["id"] for res in var_values["records"]]
        self.assertNotIn(val_jet.id, var_value_ids)

    def test_web_search_read_id_in_filtering(self):
        """Test that web_search_read filters out disallowed variables and actions when queried by ID list"""  # noqa: E501
        # Active mode is DB Only (only self.var1/self.val1 allowed)
        self.template.active_mode_id = self.mode_db.id

        # 1. Test variable values filtering by ID list
        res_vars = self.env["cx.tower.variable.value"].web_search_read(
            domain=[("id", "in", [self.val1.id, self.val2.id])],
            specification={"id": {}},
        )
        res_var_ids = [r["id"] for r in res_vars["records"]]
        self.assertIn(self.val1.id, res_var_ids)
        self.assertNotIn(self.val2.id, res_var_ids)

        # 2. Test actions filtering by ID list
        res_acts = self.env["cx.tower.jet.action"].web_search_read(
            domain=[("id", "in", [self.act1.id, self.act2.id])],
            specification={"id": {}},
        )
        res_act_ids = [r["id"] for r in res_acts["records"]]
        self.assertIn(self.act1.id, res_act_ids)
        self.assertNotIn(self.act2.id, res_act_ids)

    def test_mode_required_logic(self):
        """Test propagation and auto-assignment of mode_required."""
        # Create a jet without a mode
        jet = self.env["cx.tower.jet"].create(
            {
                "name": "Odoo Jet instance 3",
                "jet_template_id": self.template.id,
                "server_id": self.server.id,
            }
        )
        self.assertFalse(jet.mode_required)
        self.assertFalse(jet.active_mode_id)

        # Enable mode_required on the template
        self.template.write({"mode_required": True})

        # Verify it propagated to the jet and auto-assigned the mode
        self.assertTrue(jet.mode_required)
        self.assertEqual(jet.active_mode_id, self.mode_db)

        # Verify the template itself got the mode auto-assigned
        self.assertEqual(self.template.active_mode_id, self.mode_db)

        # Test constraint when no modes exist
        empty_template = self.env["cx.tower.jet.template"].create(
            {
                "name": "Empty Template",
                "reference": "empty_template",
            }
        )
        from odoo.exceptions import UserError

        with self.assertRaises(UserError):
            empty_template.write({"mode_required": True})

    def test_active_mode_id_constraint(self):
        """Test that a jet cannot be assigned a mode from a different template."""
        from odoo.exceptions import ValidationError

        # Create another template and mode
        other_template = self.env["cx.tower.jet.template"].create(
            {
                "name": "Other Template",
                "reference": "other_template",
            }
        )
        other_mode = self.env["cx.tower.jet.mode"].create(
            {
                "name": "Other Mode",
                "jet_template_id": other_template.id,
            }
        )

        # Create a jet for the standard template
        jet = self.env["cx.tower.jet"].create(
            {
                "name": "Odoo Jet instance 4",
                "jet_template_id": self.template.id,
                "server_id": self.server.id,
            }
        )

        # Try to assign the mode from the other template
        with self.assertRaises(ValidationError):
            jet.write({"active_mode_id": other_mode.id})
