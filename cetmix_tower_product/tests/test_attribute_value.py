# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.addons.cetmix_tower_server.tests.common import TestTowerCommon


class TestAttributeValue(TestTowerCommon):
    """
    Test computed fields and helper methods on product.attribute.value model
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a Tower variable and option
        cls.tower_variable = cls.env["cx.tower.variable"].create(
            {
                "name": "Test Variable",
                "reference": "test_variable",
                "variable_type": "o",  # Options type
            }
        )

        cls.tower_option = cls.env["cx.tower.variable.option"].create(
            {
                "variable_id": cls.tower_variable.id,
                "name": "Tower Option",
                "value_char": "tower_option_value",
            }
        )

        # Create a product attribute linked to Tower
        cls.linked_attribute = cls.env["product.attribute"].create(
            {
                "name": "Linked Attribute",
                "tower_variable_id": cls.tower_variable.id,
                "auto_sync_tower_values": False,
            }
        )

        # Create a Tower-linked attribute value by syncing
        cls.linked_attribute.action_sync_tower_values()
        cls.tower_value = cls.env["product.attribute.value"].search(
            [
                ("attribute_id", "=", cls.linked_attribute.id),
                ("tower_option_id", "=", cls.tower_option.id),
            ]
        )

        # Create a standard, non-linked product attribute and value
        cls.regular_attribute = cls.env["product.attribute"].create(
            {
                "name": "Regular Attribute",
            }
        )

        cls.regular_value = cls.env["product.attribute.value"].create(
            {
                "name": "Regular Value",
                "attribute_id": cls.regular_attribute.id,
            }
        )

    def test_01_computed_fields(self):
        """Test computed fields is_from_tower and tower_variable_id"""
        # Test Tower-linked value
        self.assertTrue(self.tower_value.is_from_tower)
        self.assertEqual(self.tower_value.tower_variable_id, self.tower_variable)

        # Test regular value
        self.assertFalse(self.regular_value.is_from_tower)
        self.assertFalse(self.regular_value.tower_variable_id)

    def test_02_get_tower_actual_value(self):
        """Test get_tower_actual_value method"""
        # Test Tower-linked value returns the Tower option's value_char
        tower_actual_value = self.tower_value.get_tower_actual_value()
        self.assertEqual(tower_actual_value, "tower_option_value")

        # Test regular value returns its own name
        regular_actual_value = self.regular_value.get_tower_actual_value()
        self.assertEqual(regular_actual_value, "Regular Value")

    def test_03_tower_variable_reference_field(self):
        """Test that tower_variable_reference is correctly set"""
        # Tower-linked value should have the variable reference
        self.assertEqual(self.tower_value.tower_variable_reference, "test_variable")

        # Regular value should not have a tower variable reference
        self.assertFalse(self.regular_value.tower_variable_reference)

    def test_04_tower_option_relationship(self):
        """Test the relationship with Tower option"""
        # Tower-linked value should be linked to the correct option
        self.assertEqual(self.tower_value.tower_option_id, self.tower_option)
        self.assertEqual(self.tower_value.tower_option_id.name, "Tower Option")
