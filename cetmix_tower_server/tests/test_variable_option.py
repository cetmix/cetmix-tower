from psycopg2.errors import UniqueViolation

from odoo.tests import TransactionCase


class TestTowerVariableOption(TransactionCase):
    def setUp(self):
        super().setUp()
        self.variable = self.env["cx.tower.variable"].create(
            {
                "name": "odoo_versions",
            }
        )

    def test_create_variable_option(self):
        """Test creation of a TowerVariableOption record."""
        option = self.env["cx.tower.variable.option"].create(
            {
                "name": "14.0",
                "variable_id": self.variable.id,
            }
        )
        self.assertEqual(option.name, "14.0")
        self.assertEqual(option.variable_id, self.variable)

    def test_unique_constraint(self):
        """Test the unique constraint on name and variable_id."""
        self.env["cx.tower.variable.option"].create(
            {
                "name": "17.0",
                "variable_id": self.variable.id,
            }
        )
        with self.assertRaises(UniqueViolation):
            self.env["cx.tower.variable.option"].create(
                {
                    "name": "17.0",
                    "variable_id": self.variable.id,
                }
            )
