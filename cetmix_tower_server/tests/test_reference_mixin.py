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
        # Create a new template with custom reference
        # and ensure that it's fixed according to the pattern

        new_template = self.ServerTemplate.create(
            {"name": "Such Much Template", "reference": " Some reference x*((*)) "}
        )

        self.assertEqual(new_template.reference, "some_reference_x")

        # --- 3 ---
        # Try to create another template with the same reference and ensure
        # that its reference is corrected automatically

        yet_another_template = self.ServerTemplate.create(
            {"name": "Yet another template", "reference": "some_reference_x"}
        )

        self.assertEqual(yet_another_template.reference, "some_reference_x_2")

        # -- 4 ---
        # Duplicate template and ensure that its name and reference
        # are generated properly

        yet_another_template_copy = yet_another_template.copy()

        self.assertEqual(yet_another_template_copy.name, "Yet another template (Copy)")

        self.assertEqual(
            yet_another_template_copy.reference, "yet_another_template_copy"
        )

        # -- 5 ---
        # Update reference and ensure that updated value is correct

        yet_another_template_copy.write({"reference": " Some reference x*((*)) "})
        self.assertEqual(yet_another_template_copy.reference, "some_reference_x_3")
