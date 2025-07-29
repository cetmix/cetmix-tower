# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError

from odoo.addons.cetmix_tower_server.tests.common import TestTowerCommon


class TestAttributeSafety(TestTowerCommon):
    """
    Test create and unlink constraints that protect data integrity
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create a Tower variable and option
        cls.tower_variable = cls.env["cx.tower.variable"].create(
            {
                "name": "Safety Test Variable",
                "reference": "safety_test_variable",
                "variable_type": "o",  # Options type
            }
        )

        cls.tower_option = cls.env["cx.tower.variable.option"].create(
            {
                "variable_id": cls.tower_variable.id,
                "name": "Safety Option",
                "value_char": "safety_option_value",
            }
        )

        # Create a Tower-linked attribute
        cls.linked_attribute = cls.env["product.attribute"].create(
            {
                "name": "Linked Safety Attribute",
                "tower_variable_id": cls.tower_variable.id,
                "auto_sync_tower_values": False,
            }
        )

        # Create a synced attribute value from it
        cls.linked_attribute.action_sync_tower_values()
        cls.tower_value = cls.env["product.attribute.value"].search(
            [
                ("attribute_id", "=", cls.linked_attribute.id),
                ("tower_option_id", "=", cls.tower_option.id),
            ]
        )

        # Create a standard, non-linked attribute
        cls.regular_attribute = cls.env["product.attribute"].create(
            {
                "name": "Regular Safety Attribute",
            }
        )

        # Create a value for the regular attribute
        cls.regular_value = cls.env["product.attribute.value"].create(
            {
                "name": "Regular Safety Value",
                "attribute_id": cls.regular_attribute.id,
            }
        )

    def test_01_forbid_manual_value_creation(self):
        """Test that manual creation of values for Tower-linked attributes
        is forbidden"""
        with self.assertRaises(UserError):
            self.env["product.attribute.value"].create(
                {
                    "name": "Manual Value",
                    "attribute_id": self.linked_attribute.id,
                }
            )

    def test_02_allow_manual_value_creation_for_non_linked(self):
        """Test that manual creation works for non-Tower-linked attributes"""
        new_value = self.env["product.attribute.value"].create(
            {
                "name": "Manual Regular Value",
                "attribute_id": self.regular_attribute.id,
            }
        )

        self.assertTrue(new_value.exists())
        self.assertEqual(new_value.name, "Manual Regular Value")
        self.assertEqual(new_value.attribute_id, self.regular_attribute)
        self.assertFalse(new_value.tower_option_id)
        self.assertFalse(new_value.is_from_tower)

    def test_03_forbid_unlink_of_tower_value(self):
        """Test that unlinking Tower-synchronized values is forbidden"""
        with self.assertRaises(UserError):
            self.tower_value.unlink()

        self.assertTrue(self.tower_value.exists())

    def test_04_allow_unlink_of_regular_value(self):
        """Test that unlinking regular values works normally"""
        value_id = self.regular_value.id

        self.regular_value.unlink()

        remaining_values = self.env["product.attribute.value"].search(
            [("id", "=", value_id)]
        )
        self.assertEqual(len(remaining_values), 0)

    def test_05_forbid_manual_value_creation_multi(self):
        """Test create constraint with multiple values in create_multi"""
        with self.assertRaises(UserError):
            self.env["product.attribute.value"].create(
                [
                    {
                        "name": "Valid Value 1",
                        "attribute_id": self.regular_attribute.id,
                    },
                    {
                        "name": "Invalid Value",
                        "attribute_id": self.linked_attribute.id,
                    },
                    {
                        "name": "Valid Value 2",
                        "attribute_id": self.regular_attribute.id,
                    },
                ]
            )
