from odoo.tests.common import Form

from .test_common import TestTowerCommon


class TestTowerVariables(TestTowerCommon):
    def setUp(self, *args, **kwargs):
        super(TestTowerVariables, self).setUp(*args, **kwargs)

        self.variable_dir = self.Variable.create({"name": "dir"})
        self.variable_os = self.Variable.create({"name": "os"})
        self.variable_url = self.Variable.create({"name": "url"})
        self.variable_version = self.Variable.create({"name": "version"})

    def get_variable_records(self, model=None, rec_ids=None):
        """Helper function for getting variable record values

        Args:
            model (Char): model name
            rec_ids ([Integer]): record id
        """
        domain = []
        if model:
            domain.append(("model", "=", model))
        if rec_ids:
            domain.append(
                ("res_id", "=", rec_ids)
                if isinstance(rec_ids, int)
                else ("res_id", "in", rec_ids)
            )

        res = self.VariableValues.search(domain)
        return res

    def check_variable_records(self, vals, model=None, rec_ids=None):
        """Check if variable records are correctly stored in db

        Args:
            vals (List of tuples): format ("variable_id", "value")
        """
        variable_records = self.get_variable_records(model, rec_ids)
        len_vals = len(vals)

        # Ensure correct number of records
        self.assertEqual(
            len(variable_records), len_vals, msg="Must be %s records" % str(len_vals)
        )

        # Ensure models are correct
        if model:
            record_models = variable_records.mapped("model")
            self.assertEqual(len(set(record_models)), 1, msg="Must be 1 model")
            self.assertEqual(record_models[0], model, msg="Must be %s model" % model)

        # Ensure record ids are correct
        if rec_ids:
            len_rec_ids = len(rec_ids)
            record_res_ids = variable_records.mapped("res_id")
            self.assertEqual(
                len(set(record_res_ids)),
                len_rec_ids,
                msg="Must be %s res_ids" % str(len_rec_ids),
            )
            self.assertEqual(
                set(record_res_ids),
                set(rec_ids),
                msg="rec_ids from db must match provided rec_ids",
            )

        # Check variable values
        for val in vals:
            variable_line = variable_records.filtered(
                lambda v: v.variable_id.id == val[0]
            )
            self.assertEqual(
                len(variable_line), 1, msg="Must be a single variable line"
            )
            self.assertEqual(
                variable_line.value_char,
                val[1],
                msg="Variable value does not match provided one",
            )

    def test_variable_operations(self):
        """Test variable operations"""

        # Add two variables
        with Form(self.server_test_1) as f:
            with f.variable_value_ids.new() as line:
                line.variable_id = self.variable_dir
                line.value_char = "/opt/odoo"
            with f.variable_value_ids.new() as line:
                line.variable_id = self.variable_url
                line.value_char = "example.com"
            f.save()

        vals = [
            (self.variable_url.id, "example.com"),
            (self.variable_dir.id, "/opt/odoo"),
        ]
        self.check_variable_records(
            vals=vals,
            model="cx.tower.server",
            rec_ids=[
                self.server_test_1.id,
            ],
        )

        # Add another variable and edit the existing one
        with Form(self.server_test_1) as f:
            with f.variable_value_ids.edit(1) as line:
                line.value_char = "meme.example.com"
            with f.variable_value_ids.new() as line:
                line.variable_id = self.variable_version
                line.value_char = "10.0"
            f.save()

        vals = [
            (self.variable_url.id, "meme.example.com"),
            (self.variable_dir.id, "/opt/odoo"),
            (self.variable_version.id, "10.0"),
        ]
        self.check_variable_records(
            vals=vals,
            model="cx.tower.server",
            rec_ids=[
                self.server_test_1.id,
            ],
        )  # Add another variable and edit the existing one

        # Delete two variables, add a new one
        with Form(self.server_test_1) as f:
            f.variable_value_ids.remove(index=0)
            f.variable_value_ids.remove(index=0)
            with f.variable_value_ids.new() as line:
                line.variable_id = self.variable_os
                line.value_char = "Debian"
            f.save()

        vals = [(self.variable_os.id, "Debian"), (self.variable_version.id, "10.0")]
        self.check_variable_records(
            vals=vals,
            model="cx.tower.server",
            rec_ids=[
                self.server_test_1.id,
            ],
        )
