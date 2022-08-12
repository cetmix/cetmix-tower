from odoo.tests.common import Form

from .test_common import TestTowerCommon


class TestTowerVariable(TestTowerCommon):
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

    def check_variable_values(self, vals, model=None, rec_ids=None):
        """Check if variable values are correctly stored in db

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

    def test_variable_values(self):
        """Test common variable operations"""

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
        self.check_variable_values(
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
        self.check_variable_values(
            vals=vals,
            model="cx.tower.server",
            rec_ids=[
                self.server_test_1.id,
            ],
        )

        # Delete two variables, add a new one
        with Form(self.server_test_1) as f:
            f.variable_value_ids.remove(index=0)
            f.variable_value_ids.remove(index=0)
            with f.variable_value_ids.new() as line:
                line.variable_id = self.variable_os
                line.value_char = "Debian"
            f.save()

        vals = [(self.variable_os.id, "Debian"), (self.variable_version.id, "10.0")]
        self.check_variable_values(
            vals=vals,
            model="cx.tower.server",
            rec_ids=[
                self.server_test_1.id,
            ],
        )

        # Test 'get_variable_values' function
        res = self.server_test_1.get_variable_values(["dir", "os", "url", "version"])
        self.assertEqual(len(res), 1, "Must be a single record key in the result")

        res_vars = res.get(self.server_test_1.id)
        var_dir = res_vars["dir"]
        var_os = res_vars["os"]
        var_url = res_vars["url"]
        var_version = res_vars["version"]

        self.assertIsNone(var_dir, msg="Variable 'dir' must be None")
        self.assertIsNone(var_url, msg="Variable 'url' must be None")
        self.assertEqual(var_os, "Debian", msg="Variable 'os' must be 'Debian'")
        self.assertEqual(var_version, "10.0", msg="Variable 'version' must be '10.0'")

        # ***
        # *** Test global variable values ***
        # ***

        # Create a global value for the 'dir' variable
        self.VariableValues.create(
            {"variable_id": self.variable_dir.id, "value_char": "/global/dir"}
        )
        res = self.server_test_1.get_variable_values(["dir", "os", "url", "version"])
        self.assertEqual(len(res), 1, "Must be a single record key in the result")

        res_vars = res.get(self.server_test_1.id)
        var_dir = res_vars["dir"]
        var_os = res_vars["os"]
        var_url = res_vars["url"]
        var_version = res_vars["version"]

        self.assertEqual(
            var_dir, "/global/dir", msg="Variable 'dir' must be equal to '/global/dir'"
        )
        self.assertIsNone(var_url, msg="Variable 'url' must be None")
        self.assertEqual(var_os, "Debian", msg="Variable 'os' must be 'Debian'")
        self.assertEqual(var_version, "10.0", msg="Variable 'version' must be '10.0'")

        # Now save a local value for the variable
        with Form(self.server_test_1) as f:
            with f.variable_value_ids.new() as line:
                line.variable_id = self.variable_dir
                line.value_char = "/opt/odoo"
            f.save()

        # Check
        res = self.server_test_1.get_variable_values(["dir", "os", "url", "version"])
        self.assertEqual(len(res), 1, "Must be a single record key in the result")

        res_vars = res.get(self.server_test_1.id)
        var_dir = res_vars["dir"]
        var_os = res_vars["os"]
        var_url = res_vars["url"]
        var_version = res_vars["version"]

        self.assertEqual(
            var_dir, "/opt/odoo", msg="Variable 'dir' must be equal to '/opt/odoo'"
        )
        self.assertIsNone(var_url, msg="Variable 'url' must be None")
        self.assertEqual(var_os, "Debian", msg="Variable 'os' must be 'Debian'")
        self.assertEqual(var_version, "10.0", msg="Variable 'version' must be '10.0'")

    def test_variables_in_variable_values(self):
        """Test variables in variable values
        eg
             home: /home
             user: bob
             home_dir: {{ home }}/{{ user }} --> /home/bob
        """

        # Add local variables
        with Form(self.server_test_1) as f:
            with f.variable_value_ids.new() as line:
                line.variable_id = self.variable_dir
                line.value_char = "/web"
            with f.variable_value_ids.new() as line:
                line.variable_id = self.variable_path
                line.value_char = "{{ dir }}/{{ version }}"
            with f.variable_value_ids.new() as line:
                line.variable_id = self.variable_url
                line.value_char = "{{ test_path }}/example.com"
            f.save()

        # Create a global value for the 'Version' variable
        self.VariableValues.create(
            {"variable_id": self.variable_version.id, "value_char": "10.0"}
        )

        # Check values
        res = self.server_test_1.get_variable_values(["dir", "url", "version"])
        self.assertEqual(len(res), 1, "Must be a single record key in the result")

        res_vars = res.get(self.server_test_1.id)
        var_dir = res_vars["dir"]
        var_url = res_vars["url"]
        var_version = res_vars["version"]

        self.assertEqual(var_dir, "/web", msg="Variable 'dir' must be '/web'")
        self.assertEqual(
            var_url,
            "/web/10.0/example.com",
            msg="Variable 'url' must be '/web/10.0/example.com'",
        )
        self.assertEqual(var_version, "10.0", msg="Variable 'version' must be '10.0'")

    def test_variable_values_unlink(self):
        """Ensure variable values are deleted properly
        - Create a new server
        - Add 2 variable values
        - Delete server
        - Ensure variable values are deleted
        """

        def get_value_count(variable):
            """helper function to count variable value records
            Arg: (cx.tower.variable) variable rec
            Returns: (int) record count
            """
            return self.VariableValues.search_count([("variable_id", "=", variable.id)])

        # Get variable values count before adding variables to server
        count_dir_before = get_value_count(self.variable_dir)
        count_url_before = get_value_count(self.variable_url)

        # Create new server
        server_test_var = self.Server.create(
            {
                "name": "Test Var",
                "os_id": self.os_debian_10.id,
                "ip_v4_address": "localhost",
                "ssh_username": "bob",
                "ssh_password": "pass",
            }
        )

        # Add two variables to server
        with Form(server_test_var) as f:
            with f.variable_value_ids.new() as line:
                line.variable_id = self.variable_dir
                line.value_char = "/opt/odoo"
            with f.variable_value_ids.new() as line:
                line.variable_id = self.variable_url
                line.value_char = "example.com"
            f.save()

        # Number of values should be incremented
        self.assertEqual(
            get_value_count(self.variable_dir),
            count_dir_before + 1,
            msg="Value count must be incremented!",
        )
        self.assertEqual(
            get_value_count(self.variable_url),
            count_url_before + 1,
            msg="Value count must be incremented!",
        )

        # Delete the server
        server_test_var.unlink()
        self.assertEqual(
            get_value_count(self.variable_dir),
            count_dir_before,
            msg="Value count must be same as before server creation!",
        )
        self.assertEqual(
            get_value_count(self.variable_url),
            count_url_before,
            msg="Value count must be same as before server creation!",
        )
