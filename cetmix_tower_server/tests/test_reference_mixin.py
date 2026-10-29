import re

from .common import TestTowerCommon


class TestTowerReference(TestTowerCommon):
    """Test reference generation.
    We are using ServerTemplate for that.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.plan_test_mixin = cls.Plan.create(
            {"name": "Test Plan reference mixin", "note": "Test Note reference mixin"}
        )

        cls.plan_line_reference_mixin = cls.plan_line.create(
            {
                "plan_id": cls.plan_test_mixin.id,
                "sequence": 1,
                "command_id": cls.command_list_dir.id,
            }
        )

    def test_reference_generation(self):
        """Test reference generation"""

        # --- 1 ---
        # Check if auto generated reference matches the pattern
        reference_pattern = self.ServerTemplate._get_reference_pattern()
        self.assertTrue(
            re.match(rf"{reference_pattern}", self.server_template_sample.reference),
            "Reference doesn't match template",
        )

        # --- 2 ---
        # Create a new server template with custom reference
        # and ensure that it's fixed according to the pattern
        new_template = self.ServerTemplate.create(
            {"name": "Such Much Template", "reference": " Some reference x*((*)) "}
        )
        self.assertEqual(new_template.reference, "some_reference_x")

        # --- 3 ---
        # Try to create another server template with the same reference and ensure
        # that its reference is corrected automatically
        yet_another_template = self.ServerTemplate.create(
            {"name": "Yet another template", "reference": "some_reference_x"}
        )
        self.assertEqual(yet_another_template.reference, "some_reference_x_2")

        # -- 4 ---
        # Duplicate the server template and ensure that its name and reference
        # are generated properly
        yet_another_template_copy = yet_another_template.copy()
        self.assertEqual(yet_another_template_copy.name, "Yet another template (copy)")
        self.assertEqual(
            yet_another_template_copy.reference, "yet_another_template_copy"
        )

        # -- 5 ---
        # Update reference and ensure that updated value is correct
        yet_another_template_copy.write({"reference": " Some reference x*((*)) "})
        self.assertEqual(yet_another_template_copy.reference, "some_reference_x_3")

        # -- 6 ---
        # Update template with a new name and remove reference simultaneously
        yet_another_template_copy.write({"name": "Doge so like", "reference": False})
        self.assertEqual(yet_another_template_copy.reference, "doge_so_like")

        # -- 7 ---
        # Rename the template and ensure reference is not affected
        yet_another_template_copy.write({"name": "Chad"})
        self.assertEqual(yet_another_template_copy.reference, "doge_so_like")

        # -- 8 ---
        # Remove the reference and ensure it's regenerated from the name
        yet_another_template_copy.write({"reference": False})
        self.assertEqual(yet_another_template_copy.reference, "chad")

        # -- 9 --
        # Update record with the same reference name and ensure it remains the same
        yet_another_template_copy.write({"reference": "chad"})
        self.assertEqual(yet_another_template_copy.reference, "chad")

        # -- 10 --
        # Create new template with reference set to False
        expected_reference = self.ServerTemplate._generate_or_fix_reference(
            "Such Much False Template"
        )
        new_template_with_false = self.ServerTemplate.create(
            {"name": "Such Much False Template", "reference": False}
        )
        self.assertEqual(
            new_template_with_false.reference,
            expected_reference,
            "Reference doesn't match expected one",
        )

        # -- 11 --
        # Create new template with reference and name set to a non valid symbol
        # Generic model reference should be used as a reference
        expected_reference = self.ServerTemplate._get_model_generic_reference()
        new_template_with_non_valid_reference = self.ServerTemplate.create(
            {"name": "/", "reference": "/"}
        )
        self.assertEqual(
            new_template_with_non_valid_reference.reference,
            expected_reference,
            "Reference doesn't match expected one",
        )

    def test_search_by_reference(self):
        """Search record by its reference"""

        # Create a new server template with custom reference
        server_template = self.ServerTemplate.create(
            {"name": "Such Much Template", "reference": "such_much_template"}
        )

        # Search using correct template reference
        search_result = self.ServerTemplate.get_by_reference("such_much_template")
        self.assertEqual(server_template, search_result, "Template must be found")

        # Search using malformed (case sensitive)
        search_result = self.ServerTemplate.get_by_reference("not_much_template")
        self.assertEqual(len(search_result), 0, "Result should be empty")

    def test_prepare_references_valid_input(self):
        """
        Ensure references are correctly prepared for valid input.
        """

        vals_list = [{"plan_id": self.plan_test_mixin.id}]
        result = self.plan_line._prepare_references(
            "cx.tower.plan", "plan_id", vals_list
        )

        # Verify the result contains the expected reference
        self.assertIn(
            self.plan_test_mixin.id,
            result,
            "The reference ID should be in the result.",
        )
        self.assertEqual(
            result[self.plan_test_mixin.id],
            self.plan_test_mixin.reference,
            "The reference should match the expected value.",
        )

    def test_prepare_references_invalid_model_name(self):
        """
        Check that an error is raised for an invalid model name.
        """

        vals_list = [{"plan_id": self.plan_test_mixin.id}]
        with self.assertRaises(ValueError) as cm:
            self.plan_line._prepare_references("invalid.model", "plan_id", vals_list)

        # Confirm the exception message is as expected
        self.assertEqual(
            str(cm.exception),
            "Model 'invalid.model' does not exist. Please provide a valid model name.",
            "The error message should indicate an invalid model name.",
        )

    def test_prepare_references_empty_vals_list(self):
        """
        Verify that an empty vals_list returns an empty dictionary.
        """
        result = self.plan_line._prepare_references("cx.tower.plan", "plan_id", [])
        self.assertEqual(
            result,
            {},
            "The result should be an empty dictionary when vals_list is empty.",
        )

    def test_populate_references_with_valid_input(self):
        """
        Ensure references are populated correctly in the provided values list.
        """
        vals_list = [{"plan_id": self.plan_test_mixin.id}]
        updated_vals = self.plan_line._pre_populate_references(
            "cx.tower.plan", "plan_id", vals_list
        )

        # Check the updated values contain the expected reference format
        self.assertEqual(
            updated_vals[0]["reference"],
            f"{self.plan_test_mixin.reference}_plan_line_1",
            "The reference should be correctly populated with the suffix.",
        )

    def test_populate_references_missing_field(self):
        """
        Confirm that entries missing the required field are handled properly.
        """

        vals_list_with_missing_field = [{"another_key": 123}]
        updated_vals_with_missing = self.plan_line._pre_populate_references(
            "cx.tower.plan", "plan_id", vals_list_with_missing_field
        )
        self.assertEqual(
            updated_vals_with_missing[0]["reference"],
            "no_plan_line_1",
            "Entries missing the required field should have a default reference.",
        )

    def test_populate_references_duplicate_ids(self):
        """
        Ensure that duplicate IDs in the input list are correctly
        handled and referenced.
        """
        vals_list = [
            {"plan_id": self.plan_test_mixin.id},
            {"plan_id": self.plan_test_mixin.id},
        ]
        updated_vals = self.plan_line._pre_populate_references(
            "cx.tower.plan", "plan_id", vals_list
        )

        # Verify that each duplicate entry has a unique suffix
        self.assertEqual(
            updated_vals[0]["reference"],
            f"{self.plan_test_mixin.reference}_plan_line_1",
            "The first duplicate reference should have the correct suffix.",
        )
        self.assertEqual(
            updated_vals[1]["reference"],
            f"{self.plan_test_mixin.reference}_plan_line_2",
            "The second duplicate reference should have the correct suffix.",
        )

    def test_populate_references_empty_vals_list(self):
        """
        Check that an empty input list returns an empty result
        when populating references.
        """
        updated_vals = self.plan_line._pre_populate_references(
            "cx.tower.plan", "plan_id", []
        )
        self.assertEqual(
            updated_vals,
            [],
            "The result should be an empty list when vals_list is empty.",
        )

    def test_populate_references_reference_present(self):
        """
        Check that reference is preserver when present in vals
        """

        vals_list = [
            {"reference": "my_custom_line_1"},
            {"reference": "my_custom_line_2"},
        ]
        updated_vals = self.plan_line._pre_populate_references(
            "cx.tower.plan", "plan_id", vals_list
        )
        self.assertEqual(
            updated_vals[0]["reference"],
            "my_custom_line_1",
            "Original reference must be preserved",
        )
        self.assertEqual(
            updated_vals[1]["reference"],
            "my_custom_line_2",
            "Original reference must be preserved",
        )

    def test_populate_references_mixed_scenarios(self):
        """Test mixed scenarios with existing and missing references"""
        vals_list = [
            {"reference": "my_custom_line_1"},
            {"plan_id": self.plan_test_mixin.id},  # No reference
            {"reference": "  "},  # Whitespace reference
            {"reference": ""},  # Empty reference
            {"reference": "\n_"},  # Some irrelevant symbols
        ]
        updated_vals = self.plan_line._pre_populate_references(
            "cx.tower.plan", "plan_id", vals_list
        )

        self.assertEqual(
            updated_vals[0]["reference"],
            "my_custom_line_1",
            "Original reference must be preserved",
        )
        self.assertEqual(
            updated_vals[1]["reference"],
            f"{self.plan_test_mixin.reference}_plan_line_1",
            "Missing reference should be generated",
        )
        self.assertEqual(
            updated_vals[2]["reference"],
            "no_plan_line_1",
            "Missing reference should be generated",
        )
        self.assertEqual(
            updated_vals[3]["reference"],
            "no_plan_line_2",
            "Missing reference should be generated",
        )
        self.assertEqual(
            updated_vals[4]["reference"],
            "no_plan_line_3",
            "Missing reference should be generated",
        )

    def _prepare_dependent_reference_cases(self):
        """Create each parent that rewrites child references on its own save.

        Child references are set explicitly. They differ from the generated
        ``{parent}_model_index`` pattern, which is what a same-reference save
        used to write back.

        Parents come from ``_get_dependent_model_relation_fields``:

        - flight plan: lines, and through them line actions and the action's
          variable values
        - flight plan line: actions
        - flight plan line action: variable values
        - variable: values
        - server template: variable values
        - server: variable values and files

        Variable options, jet actions, git sources and git remotes generate a
        reference from the parent when they are created. Their parent does not
        list them as dependent records, so a later parent save does not rename
        them.

        Returns:
            list[tuple]: ``(label, parent, children)`` for each parent.
        """
        cases = []

        plan = self.Plan.create(
            {"name": "Child ref plan", "reference": "child_ref_plan"}
        )
        line = self.plan_line.create(
            {
                "plan_id": plan.id,
                "sequence": 10,
                "command_id": self.command_list_dir.id,
                "reference": "keep_plan_line",
            }
        )
        action = self.plan_line_action.create(
            {
                "line_id": line.id,
                "sequence": 1,
                "condition": "==",
                "value_char": "0",
                "action": "n",
                "reference": "keep_plan_action",
            }
        )
        plan_value = self.VariableValue.create(
            {
                "variable_id": self.variable_path.id,
                "value_char": "plan-value",
                "plan_line_action_id": action.id,
                "reference": "keep_plan_value",
            }
        )
        cases.append(("flight plan", plan, [line, action, plan_value]))

        line_plan = self.Plan.create(
            {"name": "Child ref line plan", "reference": "child_ref_line_plan"}
        )
        line_parent = self.plan_line.create(
            {
                "plan_id": line_plan.id,
                "sequence": 20,
                "command_id": self.command_list_dir.id,
                "reference": "keep_line_parent",
            }
        )
        line_action = self.plan_line_action.create(
            {
                "line_id": line_parent.id,
                "sequence": 1,
                "condition": "==",
                "value_char": "0",
                "action": "n",
                "reference": "keep_line_action",
            }
        )
        cases.append(("flight plan line", line_parent, line_action))

        action_plan = self.Plan.create(
            {"name": "Child ref action plan", "reference": "child_ref_action_plan"}
        )
        action_line = self.plan_line.create(
            {
                "plan_id": action_plan.id,
                "sequence": 10,
                "command_id": self.command_list_dir.id,
                "reference": "keep_action_line",
            }
        )
        action_parent = self.plan_line_action.create(
            {
                "line_id": action_line.id,
                "sequence": 2,
                "condition": "!=",
                "value_char": "1",
                "action": "n",
                "reference": "keep_action_parent",
            }
        )
        action_value = self.VariableValue.create(
            {
                "variable_id": self.variable_os.id,
                "value_char": "action-value",
                "plan_line_action_id": action_parent.id,
                "reference": "keep_action_value",
            }
        )
        cases.append(("flight plan line action", action_parent, action_value))

        variable = self.Variable.create(
            {"name": "Child ref variable", "reference": "child_ref_variable"}
        )
        variable_value = self.VariableValue.create(
            {
                "variable_id": variable.id,
                "value_char": "global-value",
                "reference": "keep_variable_value",
            }
        )
        cases.append(("variable", variable, variable_value))

        template = self.ServerTemplate.create(
            {
                "name": "Child ref template",
                "reference": "child_ref_template",
                "ssh_port": 22,
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "os_id": self.os_debian_10.id,
            }
        )
        template_value = self.VariableValue.create(
            {
                "variable_id": self.variable_url.id,
                "value_char": "template-value",
                "server_template_id": template.id,
                "reference": "keep_template_value",
            }
        )
        cases.append(("server template", template, template_value))

        server = self.Server.create(
            {
                "name": "Child ref server",
                "reference": "child_ref_server",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "host_key": "test_key",
                "os_id": self.os_debian_10.id,
            }
        )
        server_value = self.VariableValue.create(
            {
                "variable_id": self.variable_dir.id,
                "value_char": "server-value",
                "server_id": server.id,
                "reference": "keep_server_value",
            }
        )
        server_file = self.File.create(
            {
                "name": "keep.txt",
                "reference": "keep_server_file",
                "source": "server",
                "server_id": server.id,
                "server_dir": "/var/tmp",
            }
        )
        cases.append(("server", server, [server_value, server_file]))
        return cases

    def test_same_reference_keeps_dependent_references(self):
        """Saving the current reference must not rename dependent records."""
        for label, parent, children in self._prepare_dependent_reference_cases():
            self.assertTrue(children, f"{label} has no dependent records")
            references_before = {child.id: child.reference for child in children}
            parent.write({"reference": parent.reference})
            for child in children:
                self.assertEqual(
                    child.reference,
                    references_before[child.id],
                    f"{label} child reference must stay when the parent "
                    "reference is unchanged",
                )

    def test_changed_reference_updates_dependent_references(self):
        """A new parent reference still renames its dependent records."""
        for label, parent, children in self._prepare_dependent_reference_cases():
            references_before = {child.id: child.reference for child in children}
            new_reference = f"{parent.reference}_renamed"
            parent.write({"reference": new_reference})
            self.assertEqual(parent.reference, new_reference)
            for child in children:
                self.assertNotEqual(
                    child.reference,
                    references_before[child.id],
                    f"{label} child reference must follow the new parent reference",
                )
