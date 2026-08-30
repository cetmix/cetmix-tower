# Copyright (C) 2026 Crumges
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields
from odoo.tests.common import TransactionCase


class TestJetTemplateSync(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Setup test data
        cls.variable_obj = cls.env["cx.tower.variable"]
        cls.template_obj = cls.env["cx.tower.jet.template"]
        cls.jet_obj = cls.env["cx.tower.jet"]
        cls.server_obj = cls.env["cx.tower.server"]

        # Create a test server
        cls.server = cls.server_obj.create(
            {
                "name": "Test Server",
                "ssh_username": "root",
                "ip_v4_address": "127.0.0.1",
            }
        )

        # Create some test variables
        cls.var1 = cls.variable_obj.create(
            {
                "name": "Test Var 1",
                "reference": "test_var_1",
                "variable_type": "s",
            }
        )
        cls.var2 = cls.variable_obj.create(
            {
                "name": "Test Var 2",
                "reference": "test_var_2",
                "variable_type": "s",
            }
        )

        # Create a jet template
        cls.template = cls.template_obj.create(
            {
                "name": "Test Template",
                "show_in_create_wizard": True,
                "variable_value_ids": [
                    (
                        0,
                        0,
                        {
                            "variable_id": cls.var1.id,
                            "value_char": "default_val_1",
                        },
                    )
                ],
            }
        )

    def test_01_propagation_on_create(self):
        """Test that variables are propagated from template to jet on creation"""
        # Create a jet from the template using the overridden _prepare_jet_values
        jet = self.template.create_jet(self.server, name="Test Jet 1")

        # Verify that the jet has the variable copied
        self.assertEqual(len(jet.variable_value_ids), 1)
        jet_val = jet.variable_value_ids[0]
        self.assertEqual(jet_val.variable_id, self.var1)
        self.assertEqual(jet_val.value_char, "default_val_1")

    def test_02_propagation_with_override(self):
        """Test that variables overridden during creation are not replaced
        by template defaults"""
        # Create a jet with overridden variables
        jet = self.template.create_jet(
            self.server,
            name="Test Jet 2",
            variable_values={
                "test_var_1": "overridden_val_1",
            },
        )

        # Verify that the jet has the overridden value, not the default template value
        self.assertEqual(len(jet.variable_value_ids), 1)
        jet_val = jet.variable_value_ids[0]
        self.assertEqual(jet_val.variable_id, self.var1)
        self.assertEqual(jet_val.value_char, "overridden_val_1")

    def test_03_sync_button(self):
        """Test that the sync button correctly propagates newly added
        template variables and logs to existing jets"""
        # Create a jet from the template
        jet = self.template.create_jet(self.server, name="Test Jet 3")
        self.assertEqual(len(jet.variable_value_ids), 1)

        # No pending sync initially because all variables were propagated on create
        self.assertFalse(self.template.has_pending_sync)

        # Add a new variable and a server log to the template
        command = self.env["cx.tower.command"].create(
            {
                "name": "Test command",
                "action": "ssh_command",
                "code": "echo hello",
            }
        )
        self.template.write(
            {
                "variable_value_ids": [
                    (
                        0,
                        0,
                        {
                            "variable_id": self.var2.id,
                            "value_char": "default_val_2",
                        },
                    )
                ],
                "server_log_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Sync Test Log",
                            "log_type": "command",
                            "command_id": command.id,
                        },
                    )
                ],
            }
        )

        # There should be pending sync now
        self.assertTrue(self.template.has_pending_sync)

        # Manually customize the first variable on the jet so we can verify it
        # is not overwritten
        jet.variable_value_ids.filtered(lambda v: v.variable_id == self.var1).write(
            {"value_char": "customized_val_1"}
        )

        # Run the sync action
        self.template.action_sync_to_jets()

        # No pending sync after execution
        self.assertFalse(self.template.has_pending_sync)

        # 1. Check that the new variable was synchronized
        self.assertEqual(len(jet.variable_value_ids), 2)
        jet_val1 = jet.variable_value_ids.filtered(lambda v: v.variable_id == self.var1)
        jet_val2 = jet.variable_value_ids.filtered(lambda v: v.variable_id == self.var2)
        self.assertEqual(jet_val1.value_char, "customized_val_1")
        self.assertEqual(jet_val2.value_char, "default_val_2")

        # 2. Check that the new log was synchronized
        self.assertEqual(len(jet.server_log_ids), 1)
        jet_log = jet.server_log_ids[0]
        self.assertEqual(jet_log.name, "Sync Test Log")
        self.assertEqual(jet_log.log_type, "command")
        self.assertEqual(jet_log.command_id, command)

    def test_04_wizard_onchange(self):
        """Test that the wizard pre-populates variables when the template is changed"""
        # Create with the template set, as it is required on the model
        wizard = self.env["cx.tower.jet.create.wizard"].create(
            {
                "jet_template_id": self.template.id,
            }
        )

        # By default, use_custom_variables is 'n'
        self.assertEqual(wizard.use_custom_variables, "n")
        wizard._onchange_jet_template_id_populate_variables()
        self.assertFalse(wizard.line_ids)

        # Trigger onchange manually to simulate UI behavior with
        # use_custom_variables = "y"
        wizard.use_custom_variables = "y"
        wizard._onchange_jet_template_id_populate_variables()

        # Verify populated
        self.assertTrue(wizard.line_ids)
        self.assertEqual(wizard.use_custom_variables, "y")
        self.assertEqual(len(wizard.line_ids), 1)
        self.assertEqual(wizard.line_ids[0].variable_id, self.var1)
        self.assertEqual(wizard.line_ids[0].value_char, "default_val_1")

        # Toggle back to 'n'
        wizard.use_custom_variables = "n"
        wizard._onchange_jet_template_id_populate_variables()
        self.assertFalse(wizard.line_ids)

    def test_05_wizard_default_get(self):
        """Test that the wizard defaults to 'n' (default settings) and
        empty lines"""
        WizardModel = self.env["cx.tower.jet.create.wizard"].with_context(
            default_jet_template_id=self.template.id
        )
        defaults = WizardModel.default_get(
            ["jet_template_id", "line_ids", "use_custom_variables"]
        )

        # Default should be 'n' (default settings) and no variables
        # pre-populated in lines
        self.assertEqual(defaults.get("use_custom_variables"), "n")
        self.assertFalse(defaults.get("line_ids"))

    def test_06_sync_scheduled_tasks(self):
        """Test that adding a scheduled task to a template shows pending
        sync and copies it to jets"""
        # Create a jet from the template
        jet = self.template.create_jet(self.server, name="Test Jet Tasks")
        self.assertFalse(jet.scheduled_task_ids)

        # Create a scheduled task
        command = self.env["cx.tower.command"].create(
            {
                "name": "Task command",
                "action": "ssh_command",
                "code": "echo task",
            }
        )
        task = self.env["cx.tower.scheduled.task"].create(
            {
                "name": "Template Scheduled Task",
                "action": "command",
                "command_id": command.id,
                "interval_number": 1,
                "interval_type": "days",
                "next_call": fields.Datetime.now(),
            }
        )

        # Add task to template
        self.template.write(
            {
                "scheduled_task_ids": [(4, task.id)],
            }
        )

        # Verify pending sync is True
        self.assertTrue(self.template.has_pending_sync)

        # Sync
        self.template.action_sync_to_jets()

        # Verify pending sync is False
        self.assertFalse(self.template.has_pending_sync)

        # Verify task is copied to jet
        self.assertIn(task, jet.scheduled_task_ids)

    def test_07_exclude_from_sync(self):
        """Test that a jet with exclude_from_sync=True is ignored during
        sync check and sync action"""
        # Create a jet from the template and exclude it
        jet = self.template.create_jet(self.server, name="Test Excluded Jet")
        jet.write({"exclude_from_sync": True})
        self.assertEqual(len(jet.variable_value_ids), 1)

        # Add a new variable to the template
        self.template.write(
            {
                "variable_value_ids": [
                    (
                        0,
                        0,
                        {
                            "variable_id": self.var2.id,
                            "value_char": "val_2",
                        },
                    )
                ],
            }
        )

        # has_pending_sync should be False because the jet is excluded
        self.assertFalse(self.template.has_pending_sync)

        # Run sync action
        self.template.action_sync_to_jets()

        # Jet should NOT have the new variable synced (still has 1 variable)
        self.assertEqual(len(jet.variable_value_ids), 1)
        self.assertNotIn(self.var2, jet.variable_value_ids.mapped("variable_id"))
