from psycopg2 import IntegrityError

from .common import TestTowerCommon


class TestTowerVariableOption(TestTowerCommon):
    """Test case class to validate the behavior of
    'cx.tower.variable.option' model.
    """

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
        # Test that creating another option with the same
        # 'name' and 'variable_id' raises an IntegrityError
        with self.assertRaises(
            IntegrityError,
            msg="The combination of name and variable_id must be unique.",
        ):
            self.env["cx.tower.variable.option"].create(
                {
                    "name": "17.0",
                    "variable_id": self.variable.id,
                }
            )
