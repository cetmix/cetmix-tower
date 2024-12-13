from psycopg2.errors import UniqueViolation

from .common import TestTowerCommon


class TestTowerVariableOption(TestTowerCommon):
    def setUp(self):
        super().setUp()
        self.variable = self.env["cx.tower.variable"].create(
            {
                "name": "odoo_versions",
            }
        )

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
