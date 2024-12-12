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

    def test_create_with_default_context(self):
        """Test creation of a TowerVariableOption using
        default_variable_id in context."""
        with self.env.cr.savepoint():
            context = {"default_variable_id": self.variable.id}
            option = (
                self.env["cx.tower.variable.option"]
                .with_context(context)
                .create(
                    {
                        "name": "15.0",
                    }
                )
            )
            self.assertEqual(option.variable_id, self.variable)

    def test_ondelete_cascade(self):
        """Test that deleting a variable cascades to its options."""
        option = self.env["cx.tower.variable.option"].create(
            {
                "name": "16.0",
                "variable_id": self.variable.id,
            }
        )
        self.variable.unlink()
        options = self.env["cx.tower.variable.option"].search(
            [
                ("id", "=", option.id),
            ]
        )
        self.assertFalse(
            options, "Options should be deleted when the variable is deleted."
        )

    def test_unique_constraint(self):
        """Test the unique constraint on name and variable_id."""
        self.env["cx.tower.variable.option"].create(
            {
                "name": "17.0",
                "variable_id": self.variable.id,
            }
        )
        duplicate_exists = self.env["cx.tower.variable.option"].search_count(
            [
                ("name", "=", "17.0"),
                ("variable_id", "=", self.variable.id),
            ]
        )
        self.assertEqual(
            duplicate_exists, 1, "Duplicate record exists before the second create."
        )
