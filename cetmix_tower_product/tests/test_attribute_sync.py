# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.addons.cetmix_tower_server.tests.common import TestTowerCommon


class TestAttributeSync(TestTowerCommon):
    """
    Test synchronization between Tower variables and product attributes
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a Tower variable of type 'Options'
        cls.tower_variable = cls.env["cx.tower.variable"].create(
            {
                "name": "Test Product Options",
                "reference": "test_product_options",
                "variable_type": "o",  # Options type
            }
        )

        # Create two options for this variable
        cls.option_1 = cls.env["cx.tower.variable.option"].create(
            {
                "variable_id": cls.tower_variable.id,
                "name": "Option 1",
                "value_char": "option_1",
            }
        )
        cls.option_2 = cls.env["cx.tower.variable.option"].create(
            {
                "variable_id": cls.tower_variable.id,
                "name": "Option 2",
                "value_char": "option_2",
            }
        )

        # Create a product attribute for manual syncing
        cls.manual_sync_attribute = cls.env["product.attribute"].create(
            {
                "name": "Manual Sync Test Attribute",
                "tower_variable_id": cls.tower_variable.id,
                "auto_sync_tower_values": False,
            }
        )

        # Create a product attribute for automatic syncing
        cls.auto_sync_attribute = cls.env["product.attribute"].create(
            {
                "name": "Auto Sync Test Attribute",
                "tower_variable_id": cls.tower_variable.id,
                "auto_sync_tower_values": True,
            }
        )

    def test_01_manual_sync_creates_values(self):
        """Test that manual sync creates attribute values correctly"""
        # Initial state - no values should exist
        initial_count = self.env["product.attribute.value"].search_count(
            [("attribute_id", "=", self.manual_sync_attribute.id)]
        )
        self.assertEqual(initial_count, 0)

        # Call action_sync_tower_values
        result = self.manual_sync_attribute.action_sync_tower_values()

        # Assert that exactly two product.attribute.value records are created
        final_count = self.env["product.attribute.value"].search_count(
            [("attribute_id", "=", self.manual_sync_attribute.id)]
        )
        self.assertEqual(final_count, 2)

        # Assert each new value is correctly linked to its corresponding Tower option
        values = self.env["product.attribute.value"].search(
            [("attribute_id", "=", self.manual_sync_attribute.id)]
        )

        tower_option_ids = values.mapped("tower_option_id").ids
        expected_option_ids = [self.option_1.id, self.option_2.id]
        self.assertEqual(set(tower_option_ids), set(expected_option_ids))

        # Check that names match the option names
        value_names = values.mapped("name")
        expected_names = ["Option 1", "Option 2"]
        self.assertEqual(set(value_names), set(expected_names))

        # Verify the result structure
        self.assertIn("created", result)
        self.assertEqual(len(result["created"]), 2)

    def test_02_manual_sync_is_idempotent(self):
        """Test that running manual sync twice doesn't create duplicates"""
        # First sync
        self.manual_sync_attribute.action_sync_tower_values()

        first_count = self.env["product.attribute.value"].search_count(
            [("attribute_id", "=", self.manual_sync_attribute.id)]
        )
        self.assertEqual(first_count, 2)

        # Second sync
        result = self.manual_sync_attribute.action_sync_tower_values()

        second_count = self.env["product.attribute.value"].search_count(
            [("attribute_id", "=", self.manual_sync_attribute.id)]
        )
        self.assertEqual(second_count, 2)  # Count should remain the same

        # No new values should be created in the second sync
        self.assertEqual(len(result["created"]), 0)

    def test_03_auto_sync_on_option_creation(self):
        """Test that auto sync triggers when new options are created"""
        # First, run initial sync on auto_sync_attribute
        self.auto_sync_attribute.action_sync_tower_values()

        auto_sync_initial_count = self.env["product.attribute.value"].search_count(
            [("attribute_id", "=", self.auto_sync_attribute.id)]
        )
        self.assertEqual(auto_sync_initial_count, 2)

        # Also sync manual attribute to compare
        self.manual_sync_attribute.action_sync_tower_values()

        manual_sync_initial_count = self.env["product.attribute.value"].search_count(
            [("attribute_id", "=", self.manual_sync_attribute.id)]
        )
        self.assertEqual(manual_sync_initial_count, 2)

        # Create a third option for the Tower variable
        option_3 = self.env["cx.tower.variable.option"].create(
            {
                "variable_id": self.tower_variable.id,
                "name": "Option 3",
                "value_char": "option_3",
            }
        )

        # Assert that auto_sync_attribute now automatically has three values
        auto_sync_final_count = self.env["product.attribute.value"].search_count(
            [("attribute_id", "=", self.auto_sync_attribute.id)]
        )
        self.assertEqual(auto_sync_final_count, 3)

        # Verify the new value exists and is linked correctly
        new_value = self.env["product.attribute.value"].search(
            [
                ("attribute_id", "=", self.auto_sync_attribute.id),
                ("tower_option_id", "=", option_3.id),
            ]
        )
        self.assertEqual(len(new_value), 1)
        self.assertEqual(new_value.name, "Option 3")

        # Assert that manual_sync_attribute still only has two values
        manual_sync_final_count = self.env["product.attribute.value"].search_count(
            [("attribute_id", "=", self.manual_sync_attribute.id)]
        )
        self.assertEqual(manual_sync_final_count, 2)
