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
