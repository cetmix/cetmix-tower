import re

from .common import TestTowerCommon


class TestTowerReference(TestTowerCommon):
    """Test reference generation.
    We are using ServerTemplate for that.
    """

    def setUp(self, *args, **kwargs):
        super().setUp(*args, **kwargs)

        self.plan_reference_mixin = self.Plan.create(
            {"name": "Test Plan reference mixin", "note": "Test Note reference mixin"}
        )

        self.plan_line_reference_mixin = self.plan_line.create(
            {
                "plan_id": self.plan_reference_mixin.id,
                "sequence": 1,
                "command_id": self.command_list_dir.id,
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

        vals_list = [{"plan_id": self.plan_reference_mixin.id}]
        result = self.plan_line._prepare_references(
            "cx.tower.plan", "plan_id", vals_list
        )

        # Verify the result contains the expected reference
        self.assertIn(
            self.plan_reference_mixin.id,
            result,
            "The reference ID should be in the result.",
        )
        self.assertEqual(
            result[self.plan_reference_mixin.id],
            self.plan_reference_mixin.reference,
            "The reference should match the expected value.",
        )

    def test_prepare_references_invalid_model_name(self):
        """
        Check that an error is raised for an invalid model name.
        """

        vals_list = [{"plan_id": self.plan_reference_mixin.id}]
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
        vals_list = [{"plan_id": self.plan_reference_mixin.id}]
        updated_vals = self.plan_line._populate_references(
            "cx.tower.plan", "plan_id", vals_list, suffix="TEST"
        )

        # Check the updated values contain the expected reference format
        self.assertEqual(
            updated_vals[0]["reference"],
            f"{self.plan_reference_mixin.reference}TEST_1",
            "The reference should be correctly populated with the suffix.",
        )

    def test_populate_references_missing_field(self):
        """
        Confirm that entries missing the required field are handled properly.
        """

        vals_list_with_missing_field = [{"another_key": 123}]
        updated_vals_with_missing = self.plan_line._populate_references(
            "cx.tower.plan", "plan_id", vals_list_with_missing_field, suffix="MISSING"
        )
        self.assertEqual(
            updated_vals_with_missing[0]["reference"],
            "no_MISSING_1",
            "Entries missing the required field should have a default reference.",
        )

    def test_populate_references_duplicate_ids(self):
        """
        Ensure that duplicate IDs in the input list are correctly
        handled and referenced.
        """
        vals_list = [
            {"plan_id": self.plan_reference_mixin.id},
            {"plan_id": self.plan_reference_mixin.id},
        ]
        updated_vals = self.plan_line._populate_references(
            "cx.tower.plan", "plan_id", vals_list, suffix="DUPLICATE"
        )

        # Verify that each duplicate entry has a unique suffix
        self.assertEqual(
            updated_vals[0]["reference"],
            f"{self.plan_reference_mixin.reference}DUPLICATE_1",
            "The first duplicate reference should have the correct suffix.",
        )
        self.assertEqual(
            updated_vals[1]["reference"],
            f"{self.plan_reference_mixin.reference}DUPLICATE_2",
            "The second duplicate reference should have the correct suffix.",
        )

    def test_populate_references_empty_vals_list(self):
        """
        Check that an empty input list returns an empty result
        when populating references.
        """
        updated_vals = self.plan_line._populate_references(
            "cx.tower.plan", "plan_id", [], suffix="EMPTY"
        )
        self.assertEqual(
            updated_vals,
            [],
            "The result should be an empty list when vals_list is empty.",
        )
