import re

from .common import TestTowerCommon


class TestTowerReference(TestTowerCommon):
    """Test reference generation.
    We are using ServerTemplate for that.
    """

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
