from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError

from .common import TestTowerCommon


class TestTowerVariableOption(TestTowerCommon):
    """Test case class to validate the behavior of
    'cx.tower.variable.option' model.
    """

    def setUp(self):
        super().setUp()

        self.variable_odoo_versions = self.Variable.create(
            {
                "name": "odoo_versions",
                "variable_type": "o",
            }
        )

        self.variable_option_17_0 = self.VariableOption.create(
            {
                "name": "17.0",
                "value_char": "17.0",
                "variable_id": self.variable_odoo_versions.id,
            }
        )

        self.variable_option_18_0 = self.VariableOption.create(
            {
                "name": "18.0",
                "value_char": "18.0",
                "variable_id": self.variable_odoo_versions.id,
            }
        )

    def test_unique_constraint(self):
        """Test the unique constraint on name and variable_id."""

        # Test that creating another option with the same
        # 'name' and 'variable_id' raises an IntegrityError
        with self.assertRaises(
            IntegrityError,
            msg="The combination of name and variable_id must be unique.",
        ):
            self.env["cx.tower.variable.option"].create(
                {
                    "name": "17.0",
                    "value_char": "17.0",
                    "variable_id": self.variable_odoo_versions.id,
                }
            )

    def test_variable_value_set_from_option(self):
        """Test that a variable value can be set from an option."""

        variable_value = self.VariableValue.create(
            {
                "server_id": self.server_test_1.id,
                "variable_id": self.variable_odoo_versions.id,
            }
        )

        # -- 1 --
        # Set value_char to an existing option
        variable_value.value_char = "17.0"
        self.assertEqual(
            variable_value.option_id,
            self.variable_option_17_0,
        )

        # -- 2 --
        # Set value_char to a non-existing option
        with self.assertRaises(ValidationError):
            variable_value.value_char = "29.0"
