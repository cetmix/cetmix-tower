from odoo.tests import common

from ..models.tools import CHARS, generate_random_id


class TestTools(common.TransactionCase):
    """Test class for tools module."""

    def test_generate_random_id(self):
        """Test random id generation"""
        # Test single section
        result = generate_random_id()
        self.assertEqual(len(result), 4)  # Default length is 4
        self.assertTrue(all(c in CHARS for c in result))  # All chars from CHARS

        # Test multiple sections
        result = generate_random_id(sections=2)
        sections = result.split("-")
        self.assertEqual(len(sections), 2)
        self.assertTrue(all(len(s) == 4 for s in sections))
        self.assertTrue(all(c in CHARS for s in sections for c in s))

        # Test custom population
        result = generate_random_id(population=6)
        self.assertEqual(len(result), 6)

        # Test custom separator
        result = generate_random_id(sections=2, separator="_")
        self.assertIn("_", result)
        self.assertEqual(len(result.split("_")), 2)

        # Test invalid inputs
        self.assertIsNone(generate_random_id(sections=0))
        self.assertIsNone(generate_random_id(population=-1))

        # Test empty separator
        result = generate_random_id(sections=3, separator="")
        self.assertEqual(len(result), 12)  # 3 sections of 4 chars with no separator
