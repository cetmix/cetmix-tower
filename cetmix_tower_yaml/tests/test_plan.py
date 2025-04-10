from odoo.tests import TransactionCase


class TestTowerPlan(TransactionCase):
    @classmethod
    def setUpClass(cls, *args, **kwargs):
        super().setUpClass(*args, **kwargs)

        cls.Plan = cls.env["cx.tower.plan"]

    def test_plan_create_from_yaml(self):
        """Test plan creation from YAML."""

        plan_yaml = """cetmix_tower_model: plan
access_level: manager
reference: test_plan_from_yaml
name: 'Test Plan From Yaml'
allow_parallel_run: false
color: 0
tag_ids:
- reference: doge_test_plan_tag
  name: Doge Test Plan Tag
  color: 1
on_error_action: e
custom_exit_code: 0
line_ids:
- sequence: 5
  condition: false
  use_sudo: false
  path: /such/much/{{ test_plan_dir }}
  command_id:
    access_level: manager
    reference: very_much_command_test
    name: Very much command
    action: ssh_command
    allow_parallel_run: false
    note: false
    code: Such much code
    variable_ids:
    - cetmix_tower_model: variable
      reference: test_plan_dir
      name: Test Plan Directory
  action_ids:
  - sequence: 1
    condition: ==
    value_char: '0'
    action: n
    custom_exit_code: 0
    variable_value_ids:
    - cetmix_tower_model: variable_value
      variable_id:
        cetmix_tower_yaml_version: 1
        cetmix_tower_model: variable
        reference: test_plan_branch
        name: Test Plan Branch
      value_char: production
    - cetmix_tower_model: variable_value
      variable_id:
        cetmix_tower_yaml_version: 1
        cetmix_tower_model: variable
        reference: test_plan_some_unique_variable
        name: Test Plan Some Unique Variable
      value_char: 'Final Value'
  - cetmix_tower_model: plan_line_action
    access_level: manager
    sequence: 2
    condition: '>'
    value_char: '0'
    action: ec
    custom_exit_code: 255
    variable_value_ids: false
  variable_ids: false
"""
        # -- 1 --
        # Create plan from YAML
        plan_form_yaml = self.Plan.create(
            {"name": "Name Placeholder", "yaml_code": plan_yaml}
        )
        self.assertEqual(
            plan_form_yaml.reference,
            "test_plan_from_yaml",
            "Reference is not set from YAML",
        )
        # Name should be set from YAML
        self.assertEqual(
            plan_form_yaml.name, "Test Plan From Yaml", "Name is not set from YAML"
        )

        # -- 2 --
        # Check plan tags
        plan_tags = plan_form_yaml.tag_ids
        self.assertEqual(len(plan_tags), 1)
        self.assertEqual(plan_tags.name, "Doge Test Plan Tag")

        # -- 3 --
        # Check plan lines
        plan_lines = plan_form_yaml.line_ids
        self.assertEqual(len(plan_lines), 1, "Line count is not 1")
        self.assertFalse(plan_lines.condition, "Condition is not false")
        self.assertEqual(
            plan_lines.path,
            "/such/much/{{ test_plan_dir }}",
            "Path is not set from YAML",
        )
        self.assertEqual(
            plan_lines.command_id.reference,
            "very_much_command_test",
            "Command reference is not set from YAML",
        )
        self.assertEqual(
            plan_lines.command_id.name,
            "Very much command",
            "Command name is not set from YAML",
        )
        self.assertEqual(
            plan_lines.command_id.action,
            "ssh_command",
            "Command action is not set from YAML",
        )
        self.assertFalse(
            plan_lines.command_id.allow_parallel_run,
            "Command allow parallel run is not set from YAML",
        )
        self.assertFalse(
            plan_lines.command_id.note, "Command note is not set from YAML"
        )
        self.assertEqual(
            plan_lines.command_id.variable_ids.mapped("reference"),
            ["test_plan_dir"],
            "Command variable ids is not set from YAML",
        )
        self.assertEqual(
            plan_lines.command_id.access_level,
            "2",
            "Command access level is not set from YAML",
        )

        # -- 4 --
        # Check plan line actions
        plan_actions = plan_form_yaml.line_ids.action_ids
        self.assertEqual(len(plan_actions), 2, "Action count is not 2")
        self.assertEqual(
            plan_actions[0].condition, "==", "First action condition is not equal"
        )
        self.assertEqual(
            plan_actions[0].value_char, "0", "First action value char is not 0"
        )
        self.assertEqual(plan_actions[0].action, "n", "First action action is not n")
        self.assertEqual(
            plan_actions[0].custom_exit_code,
            0,
            "First action custom exit code is not 0",
        )
        self.assertEqual(
            len(plan_actions[0].variable_value_ids),
            2,
            "Number of variable value ids is not correct",
        )
        self.assertEqual(
            plan_actions[0].variable_value_ids.mapped("value_char"),
            ["production", "Final Value"],
            "Variable value chars are not correct",
        )
        self.assertEqual(
            plan_actions[1].condition, ">", "Second action condition is not greater"
        )
        self.assertEqual(
            plan_actions[1].value_char, "0", "Second action value char is not 0"
        )
        self.assertEqual(plan_actions[1].action, "ec", "Second action action is not ec")
        self.assertEqual(
            plan_actions[1].custom_exit_code,
            255,
            "Second action custom exit code is not 255",
        )
        self.assertFalse(
            plan_actions[1].variable_value_ids,
            "Second action variable value ids is not false",
        )
