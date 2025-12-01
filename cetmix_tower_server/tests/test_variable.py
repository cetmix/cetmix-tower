# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo import _, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form
from odoo.tools.misc import mute_logger

from .common import TestTowerCommon


class TestTowerVariable(TestTowerCommon):
    """Testing variables and variable values."""

    def check_variable_values(self, vals, server_ids=None):
        """Check if variable values are correctly stored in db

        Args:
            vals (List of tuples): format ("variable_id", "value")
            server_id (cx.tower.server()): Servers those variables belong to.
        """
        if server_ids:
            variable_records = server_ids.variable_value_ids
        else:
            variable_records = self.VariableValue.search([("is_global", "=", True)])
        len_vals = len(vals)

        # Ensure correct number of records
        self.assertEqual(
            len(variable_records), len_vals, msg=f"Must be {str(len_vals)} records"
        )

        # Check variable values
        for val in vals:
            variable_line = variable_records.filtered(
                lambda v, val=val: v.variable_id.id == val[0]
            )
            self.assertEqual(
                len(variable_line), 1, msg="Must be a single variable line"
            )
            expected_value = val[1] or False
            self.assertEqual(
                variable_line.value_char,
                expected_value,
                msg="Variable value does not match provided one",
            )

    def test_variable_values(self):
        """Test common variable operations"""

        # -- 1 --
        #  Server specific variables

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
        self.check_variable_values(vals=vals, server_ids=self.server_test_1)

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
        self.check_variable_values(vals=vals, server_ids=self.server_test_1)

        # Delete two variables, add a new one
        with Form(self.server_test_1) as f:
            f.variable_value_ids.remove(index=0)
            f.variable_value_ids.remove(index=0)
            with f.variable_value_ids.new() as line:
                line.variable_id = self.variable_os
                line.value_char = "Debian"

            # Add an empty variable value
            with f.variable_value_ids.new() as line:
                line.variable_id = self.variable_url
            f.save()

        vals = [
            (self.variable_os.id, "Debian"),
            (self.variable_version.id, "10.0"),
            (self.variable_url.id, False),
        ]
        self.check_variable_values(vals=vals, server_ids=self.server_test_1)

        # Test 'get_variable_values' function
        res = self.server_test_1.get_variable_values(
            ["test_dir", "test_os", "test_url", "test_version"]
        )
        self.assertEqual(len(res), 1, "Must be a single record key in the result")

        res_vars = res.get(self.server_test_1.id)
        var_dir = res_vars["test_dir"]
        var_os = res_vars["test_os"]
        var_url = res_vars["test_url"]
        var_version = res_vars["test_version"]

        self.assertIsNone(var_dir, msg="Variable 'dir' must be None")
        self.assertFalse(var_url, msg="Variable 'url' must be False")
        self.assertEqual(var_os, "Debian", msg="Variable 'os' must be 'Debian'")
        self.assertEqual(var_version, "10.0", msg="Variable 'version' must be '10.0'")

        # -- 2 --
        # Test global variable values

        # Create a global value for the 'dir' variable
        self.VariableValue.create(
            {"variable_id": self.variable_dir.id, "value_char": "/global/dir"}
        )
        res = self.server_test_1.get_variable_values(
            ["test_dir", "test_os", "test_url", "test_version"]
        )
        self.assertEqual(len(res), 1, "Must be a single record key in the result")

        res_vars = res.get(self.server_test_1.id)
        var_dir = res_vars["test_dir"]
        var_os = res_vars["test_os"]
        var_url = res_vars["test_url"]
        var_version = res_vars["test_version"]

        self.assertEqual(
            var_dir, "/global/dir", msg="Variable 'dir' must be equal to '/global/dir'"
        )
        self.assertFalse(var_url, msg="Variable 'url' must be False")
        self.assertEqual(var_os, "Debian", msg="Variable 'os' must be 'Debian'")
        self.assertEqual(var_version, "10.0", msg="Variable 'version' must be '10.0'")

        # Now save a local value for the variable
        with Form(self.server_test_1) as f:
            with f.variable_value_ids.new() as line:
                line.variable_id = self.variable_dir
                line.value_char = "/opt/odoo"
            f.save()

        # Check
        res = self.server_test_1.get_variable_values(
            ["test_dir", "test_os", "test_url", "test_version"]
        )
        self.assertEqual(len(res), 1, "Must be a single record key in the result")

        res_vars = res.get(self.server_test_1.id)
        var_dir = res_vars["test_dir"]
        var_os = res_vars["test_os"]
        var_url = res_vars["test_url"]
        var_version = res_vars["test_version"]

        self.assertEqual(
            var_dir, "/opt/odoo", msg="Variable 'dir' must be equal to '/opt/odoo'"
        )
        self.assertFalse(var_url, msg="Variable 'url' must be False")
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
                line.value_char = "{{ test_dir }}/{{ test_version }}"
            with f.variable_value_ids.new() as line:
                line.variable_id = self.variable_url
                line.value_char = "{{ test_path_ }}/example.com"
            f.save()

        # Create a global value for the 'Version' variable
        self.VariableValue.create(
            {"variable_id": self.variable_version.id, "value_char": "10.0"}
        )

        # Check values
        res = self.server_test_1.get_variable_values(
            ["test_dir", "test_url", "test_version"]
        )
        self.assertEqual(len(res), 1, "Must be a single record key in the result")

        res_vars = res.get(self.server_test_1.id)
        var_dir = res_vars["test_dir"]
        var_url = res_vars["test_url"]
        var_version = res_vars["test_version"]

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
            return self.VariableValue.search_count([("variable_id", "=", variable.id)])

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

    def test_variable_value_toggle_global(self):
        """Test what happens when variable value 'global' setting is togged"""

        variable_meme = self.Variable.create({"name": "meme"})
        variable_value_pepe = self.VariableValue.create(
            {"variable_id": variable_meme.id, "value_char": "Pepe"}
        )

        self.assertEqual(
            variable_value_pepe.is_global, True, msg="Value 'Pepe' must be global"
        )

        # Test `_check_is_global` function
        self.assertEqual(
            variable_value_pepe._check_is_global(),
            True,
            msg="Value 'Pepe' must be global",
        )

        # Try to create another global value for the same variable
        with self.assertRaises(ValidationError) as err:
            self.VariableValue.create(
                {"variable_id": variable_meme.id, "value_char": "Doge"}
            )

        # We check the message in order to ensure that
        # exception was raised by the correct event.
        self.assertEqual(
            err.exception.args[0],
            _("Only one global value can be defined for variable 'meme'"),
            msg="Error message doesn't match. Check if you have modified it in code:"
            "models/cx_tower_server.py",
        )

        # Try to disable 'global' for a global variable explicitly
        with self.assertRaises(ValidationError) as err:
            variable_value_pepe.is_global = False

        # We check the message in order to ensure that
        # exception was raised by the correct event.
        self.assertEqual(
            err.exception.args[0],
            _(
                "Cannot change 'global' status for "
                "'meme' with value 'Pepe'."
                "\nTry to assigns it to a record instead."
            ),
            msg="Error message doesn't match. Check if you have modified it in code:"
            "models/cx_tower_server.py",
        )

    def test_system_variable_server_type_values(self):
        """Test system variables of `server` type"""

        # Modify server record for testing
        self.server_test_1.ip_v6_address = "suchmuchipv6"
        self.server_test_1.url = "meme.example.com"
        self.server_test_1.partner_id = (
            self.env["res.partner"].create({"name": "Pepe Frog"}).id
        )

        # Create new command with system variables
        command = self.Command.create(
            {
                "name": "Super System Command",
                "code": "echo {{ tower.server.name }} "
                "{{ tower.server.username}} "
                "{{ tower.server.partner_name }} "
                "{{ tower.server.ipv4 }} "
                "{{ tower.server.ipv6 }} "
                "{{ tower.server.url }} ",
            }
        )

        # Get variables
        variables = command.get_variables().get(str(command.id))
        # Get variable values
        variable_values = self.server_test_1.get_variable_values(variables).get(
            self.server_test_1.id
        )

        # Check values
        self.assertEqual(
            variable_values["tower"]["server"]["name"],
            self.server_test_1.name,
            "System variable doesn't match server property",
        )
        self.assertEqual(
            variable_values["tower"]["server"]["reference"],
            self.server_test_1.reference,
            "System variable doesn't match server property",
        )
        self.assertEqual(
            variable_values["tower"]["server"]["username"],
            self.server_test_1.ssh_username,
            "System variable doesn't match server property",
        )
        self.assertEqual(
            variable_values["tower"]["server"]["username"],
            self.server_test_1.ssh_username,
            "System variable doesn't match server property",
        )
        self.assertEqual(
            variable_values["tower"]["server"]["partner_name"],
            self.server_test_1.partner_id.name,
            "System variable doesn't match server property",
        )
        self.assertEqual(
            variable_values["tower"]["server"]["ipv4"],
            self.server_test_1.ip_v4_address,
            "System variable doesn't match server property",
        )
        self.assertEqual(
            variable_values["tower"]["server"]["ipv6"],
            self.server_test_1.ip_v6_address,
            "System variable doesn't match server property",
        )
        self.assertEqual(
            variable_values["tower"]["server"]["url"],
            self.server_test_1.url,
            "System variable doesn't match server property",
        )

    @patch(
        "odoo.addons.cetmix_tower_server.models.cx_tower_variable_mixin.fields.Datetime.now",
        return_value=fields.Datetime.now(),
    )
    @patch(
        "odoo.addons.cetmix_tower_server.models.cx_tower_variable_mixin.fields.Date.today",
        return_value=fields.Date.today(),
    )
    @patch(
        "odoo.addons.cetmix_tower_server.models.cx_tower_variable_mixin.uuid.uuid4",
        return_value="suchmuchuuid4",
    )
    def test_system_variable_tools_type_values(self, mock_uuid4, mock_today, mock_now):
        """Test system variables of `tools` type"""

        # Create new command with system variables
        command = self.Command.create(
            {"name": "Super System Command", "code": "echo {{ tower.tools.uuid}}"}
        )

        # Get variables
        variables = command.get_variables().get(str(command.id))
        # Get variable values
        variable_values = self.server_test_1.get_variable_values(variables).get(
            self.server_test_1.id
        )

        # Check values
        self.assertEqual(
            variable_values["tower"]["tools"]["uuid"],
            mock_uuid4.return_value,
            "System variable doesn't match result provided by tools",
        )
        self.assertEqual(
            variable_values["tower"]["tools"]["today"],
            str(mock_today.return_value),
            "System variable doesn't match result provided by tools",
        )
        self.assertEqual(
            variable_values["tower"]["tools"]["now"],
            str(mock_now.return_value),
            "System variable doesn't match result provided by tools",
        )
        self.assertEqual(
            variable_values["tower"]["tools"]["today_underscore"],
            str(mock_today.return_value)
            .replace("-", "_")
            .replace(" ", "_")
            .replace(":", "_")
            .replace(".", "_")
            .replace("/", "_"),
            "System variable doesn't match result provided by tools",
        )
        self.assertEqual(
            variable_values["tower"]["tools"]["now_underscore"],
            str(mock_now.return_value)
            .replace("-", "_")
            .replace(":", "_")
            .replace(" ", "_")
            .replace(".", "_")
            .replace("/", "_"),
            "System variable doesn't match result provided by tools",
        )

    def test_make_value_pythonic(self):
        """Test making variable values 'pythonic`"""

        # Number
        value = 12.34
        expected_value = '"12.34"'
        result_value = self.Command._make_value_pythonic(value)

        self.assertEqual(
            expected_value, result_value, "Result value doesn't match expected"
        )

        # Text
        value = "Doge much like"
        expected_value = '"Doge much like"'
        result_value = self.Command._make_value_pythonic(value)

        self.assertEqual(
            expected_value, result_value, "Result value doesn't match expected"
        )

        # Boolean
        value = True
        expected_value = True
        result_value = self.Command._make_value_pythonic(value)

        self.assertEqual(
            expected_value, result_value, "Result value doesn't match expected"
        )

        # None
        value = None
        expected_value = None
        result_value = self.Command._make_value_pythonic(value)

        self.assertEqual(
            expected_value, result_value, "Result value doesn't match expected"
        )

        # Dict
        value = {"doge": {"likes": "memes", "much": 200}}
        expected_value = {"doge": {"likes": '"memes"', "much": '"200"'}}
        result_value = self.Command._make_value_pythonic(value)

        self.assertEqual(
            expected_value, result_value, "Result value doesn't match expected"
        )

    def test_get_by_variable_reference(self):
        """Test getting variable values by variable reference"""

        variable_meme = self.Variable.create(
            {"name": "Meme Variable", "reference": "meme_variable"}
        )
        global_value = self.VariableValue.create(
            {"variable_id": variable_meme.id, "value_char": "Memes Globalvs"}
        )

        # -- 1 -- Get value for Server with no server value defined
        server_result = self.VariableValue.get_by_variable_reference(
            variable_meme.reference, server_id=self.server_test_1.id
        )
        self.assertIsNone(server_result.get("server"))
        self.assertIsNone(server_result.get("server_template"))
        self.assertEqual(server_result.get("global"), global_value.value_char)

        # -- 2 -- Add server value and try again
        server_value = self.VariableValue.create(
            {
                "variable_id": variable_meme.id,
                "value_char": "Memes Servervs",
                "server_id": self.server_test_1.id,
            }
        )
        server_result = self.VariableValue.get_by_variable_reference(
            variable_meme.reference, server_id=self.server_test_1.id
        )
        self.assertEqual(server_result.get("server"), server_value.value_char)
        self.assertEqual(server_result.get("global"), global_value.value_char)
        self.assertIsNone(server_result.get("server_template"))

        # -- 3 -- Do not fetch global value now
        server_result = self.VariableValue.get_by_variable_reference(
            variable_meme.reference, server_id=self.server_test_1.id, check_global=False
        )
        self.assertIsNone(server_result.get("global"))
        self.assertEqual(server_result.get("server"), server_value.value_char)
        self.assertIsNone(server_result.get("server_template"))

        # -- 4 -- Check server template value
        server_template_value = self.VariableValue.create(
            {
                "variable_id": variable_meme.id,
                "value_char": "Memes Servervs Templatvs",
                "server_template_id": self.server_template_sample.id,
            }
        )
        server_result = self.VariableValue.get_by_variable_reference(
            variable_meme.reference, server_template_id=self.server_template_sample.id
        )
        self.assertEqual(server_result.get("global"), global_value.value_char)
        self.assertIsNone(server_result.get("server"))
        self.assertEqual(
            server_result.get("server_template"), server_template_value.value_char
        )

    def test_single_assignment(self):
        """Test that a variable can only be assigned to one model at a time."""
        # Create a variable value assigned to the server
        variable_value = self.env["cx.tower.variable.value"].create(
            {
                "variable_id": self.variable_os.id,
                "value_char": "Branch = Main",
                "server_id": self.server_test_1.id,
            }
        )

        # Try to assign the same variable value to
        # server template and expect a ValidationError
        with self.assertRaises(ValidationError):
            variable_value.write({"server_template_id": self.server_template_sample.id})

        # Try to assign the same variable value to
        # plan line action and expect a ValidationError
        with self.assertRaises(ValidationError):
            variable_value.write({"plan_line_action_id": self.plan_line_1_action_1.id})

    def test_unique_assignment(self):
        """Test that the same variable value cannot be
        assigned multiple times to the same record.
        """

        # Create a variable
        variable = self.env["cx.tower.variable"].create(
            {"name": "Environment Type", "note": "The environment type for the server."}
        )

        # Create a server
        server = self.env["cx.tower.server"].create(
            {
                "name": "Test Server",
                "ip_v4_address": "127.0.0.1",
                "ssh_username": "testuser",
                "ssh_password": "testpassword",
                "ssh_auth_mode": "p",
            }
        )

        # Create a variable value for the server
        self.env["cx.tower.variable.value"].create(
            {
                "variable_id": variable.id,
                "value_char": "Production",
                "server_id": server.id,
            }
        )

        # Try to create a second variable value with the same variable and server
        with (
            mute_logger("odoo.sql_db"),
            self.assertRaises(
                IntegrityError,
                msg="A variable value cannot be assigned "
                "multiple times to the same server.",
            ),
        ):
            self.env["cx.tower.variable.value"].create(
                {
                    "variable_id": variable.id,
                    "value_char": "Production",
                    "server_id": server.id,
                }
            )

    def test_value_access_level_consistency(self):
        """Test that variable value access level cannot be lower
        than variable access level."""

        # Create test servers
        server_2 = self.Server.create(
            {
                "name": "Test Server 2",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "os_id": self.os_debian_10.id,
            }
        )

        server_3 = self.Server.create(
            {
                "name": "Test Server 3",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "os_id": self.os_debian_10.id,
            }
        )

        # Create a variable with access level "2"
        variable_restricted = self.Variable.create(
            {
                "name": "restricted_variable",
                "access_level": "2",
            }
        )

        # Should succeed: value with same access level as variable
        try:
            self.VariableValue.create(
                {
                    "variable_id": variable_restricted.id,
                    "value_char": "test_value1",
                    "access_level": "2",
                    "is_global": True,
                }
            )
        except ValidationError:
            self.fail("Should allow creating value with same access level as variable")

        # Should succeed: value with higher access level than variable
        try:
            self.VariableValue.create(
                {
                    "variable_id": variable_restricted.id,
                    "value_char": "test_value2",
                    "access_level": "3",
                    "server_id": server_2.id,
                }
            )
        except ValidationError:
            self.fail(
                "Should allow creating value with higher access level than variable"
            )

        # Should fail: value with lower access level than variable
        with self.assertRaises(
            ValidationError,
            msg="Should not allow creating value with lower access level than variable",
        ):
            self.VariableValue.create(
                {
                    "variable_id": variable_restricted.id,
                    "value_char": "test_value3",
                    "access_level": "1",
                    "server_id": server_3.id,
                }
            )

        # Test updating existing value's access level
        value = self.VariableValue.create(
            {
                "variable_id": self.variable_dir.id,  # Using a different variable
                "value_char": "test_value4",
                "access_level": "2",
                "server_id": server_3.id,
            }
        )

        # Should fail: updating to lower access level than variable
        with self.assertRaises(
            ValidationError,
            msg="Should not allow updating value to lower access level than variable",
        ):
            value.write({"access_level": "1"})

        # Should succeed: updating to higher access level than variable
        try:
            value.write({"access_level": "3"})
        except ValidationError:
            self.fail(
                "Should allow updating value to higher access level than variable"
            )

    def test_variable_access_rights(self):
        """Test access rights for variables based on access levels and user roles."""

        # Create variables with different access levels
        variable_level_1 = self.Variable.create(
            {
                "name": "Level 1 Variable",
                "access_level": "1",
            }
        )

        variable_level_2 = self.Variable.create(
            {
                "name": "Level 2 Variable",
                "access_level": "2",
            }
        )

        variable_level_3 = self.Variable.create(
            {
                "name": "Level 3 Variable",
                "access_level": "3",
            }
        )
        manager2 = self.Users.create(
            {
                "name": "Manager 2",
                "login": "manager2@example.com",
                "groups_id": [(4, self.group_manager.id)],
            }
        )

        # Test User Access
        # ---------------
        # Should see level 1 variables
        records = self.Variable.with_user(self.user).search(
            [
                (
                    "id",
                    "in",
                    [variable_level_1.id, variable_level_2.id, variable_level_3.id],
                )
            ]
        )
        self.assertEqual(len(records), 1, "User should only see level 1 variables")
        self.assertEqual(
            records.id, variable_level_1.id, "User should only see level 1 variables"
        )

        # Test Manager Access
        # -----------------
        # Should see level 1 and 2 variables
        records = self.Variable.with_user(self.manager).search(
            [
                (
                    "id",
                    "in",
                    [variable_level_1.id, variable_level_2.id, variable_level_3.id],
                )
            ]
        )
        self.assertEqual(len(records), 2, "Manager should see level 1 and 2 variables")
        self.assertIn(
            variable_level_1.id, records.ids, "Manager should see level 1 variables"
        )
        self.assertIn(
            variable_level_2.id, records.ids, "Manager should see level 2 variables"
        )

        # Test Manager Write Access
        # -----------------------
        # Create a variable as manager
        manager_variable = self.Variable.with_user(self.manager).create(
            {
                "name": "Manager Created Variable",
                "access_level": "2",
            }
        )

        # Manager should be able to modify their own variable
        try:
            manager_variable.with_user(self.manager).write({"name": "Updated Name"})
        except AccessError:
            self.fail("Manager should be able to modify their own variables")

        # Manager should not be able to modify another manager's variable
        manager2_variable = self.Variable.with_user(manager2).create(
            {
                "name": "Other Manager Variable",
                "access_level": "2",
            }
        )

        with self.assertRaises(AccessError):
            manager2_variable.with_user(self.manager).write({"name": "Try Update"})

        # Manager should not be able to create level 3 variable
        with self.assertRaises(AccessError):
            self.Variable.with_user(self.manager).create(
                {
                    "name": "Try Level 3",
                    "access_level": "3",
                }
            )

        # Test Root Access
        # --------------
        # Root should see all variables
        records = self.Variable.with_user(self.root).search(
            [
                (
                    "id",
                    "in",
                    [variable_level_1.id, variable_level_2.id, variable_level_3.id],
                )
            ]
        )
        self.assertEqual(len(records), 3, "Root should see all variables")

        # Root should be able to create any level variable
        try:
            self.Variable.with_user(self.root).create(
                {
                    "name": "Root Level 3",
                    "access_level": "3",
                }
            )
        except AccessError:
            self.fail("Root should be able to create any level variable")

        # Root should be able to modify any variable
        try:
            variable_level_3.with_user(self.root).write({"name": "Updated by Root"})
        except AccessError:
            self.fail("Root should be able to modify any variable")

    def test_validate_value(self):
        """Test variable value validation"""
        # Create variable with validation pattern
        variable_with_pattern = self.Variable.create(
            {
                "name": "Test Pattern",
                "validation_pattern": "^[a-z0-9]+$",
                "validation_message": "Only lowercase letters and numbers allowed",
            }
        )

        # Test valid values
        valid_value = "abc123"
        is_valid, message = variable_with_pattern._validate_value(valid_value)
        self.assertTrue(is_valid, "Value should be valid")
        self.assertIsNone(message, "No message should be returned for valid value")

        # Test invalid values
        invalid_value = "ABC123!"
        is_valid, message = variable_with_pattern._validate_value(invalid_value)
        self.assertFalse(is_valid, "Value should be invalid")
        self.assertEqual(
            message,
            f"Variable: {variable_with_pattern.name}, Value: {invalid_value}\n"
            "Only lowercase letters and numbers allowed",
            "Invalid value message doesn't match",
        )

        # Test empty value
        is_valid, message = variable_with_pattern._validate_value(None)
        self.assertTrue(is_valid, "Empty value should be valid")
        self.assertIsNone(message, "No message should be returned for empty value")

        # Test variable without pattern
        variable_no_pattern = self.Variable.create(
            {
                "name": "No Pattern",
            }
        )
        test_value = "Any Value!"
        is_valid, message = variable_no_pattern._validate_value(test_value)
        self.assertTrue(is_valid, "Value should be valid when no pattern is set")
        self.assertIsNone(
            message, "No message should be returned when no pattern is set"
        )

        # Test default validation message
        variable_default_message = self.Variable.create(
            {
                "name": "Default Message",
                "validation_pattern": "^[a-z]+$",
            }
        )
        invalid_value = "123"
        is_valid, message = variable_default_message._validate_value(invalid_value)
        self.assertFalse(is_valid, "Value should be invalid")
        self.assertEqual(
            message,
            f"Variable: {variable_default_message.name}, Value: {invalid_value}\n"
            f"{variable_default_message.DEFAULT_VALIDATION_MESSAGE}",
            "Default validation message doesn't match",
        )


class TestVariableReferenceRename(TestTowerCommon):
    """Ensure variable rename updates all Jinja references using shared fixtures."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.ref_old = cls.variable_version.reference
        cls.ref_new = "software_version"

        cls.command = cls.Command.create(
            {
                "name": "Show version (test)",
                "code": f"echo {{ {{ {cls.ref_old} }} }}",
                "variable_ids": [(6, 0, [cls.variable_version.id])],
            }
        )

        cls.file = cls.File.create(
            {
                "name": "test_version.txt",
                "server_dir": "/tmp",
                "code": f"{{ {{ {cls.ref_old} }} }}",
                "variable_ids": [(6, 0, [cls.variable_version.id])],
            }
        )

    def _rename(self):
        """Rename variable and invalidate caches for records under test."""
        self.variable_version.write({"reference": self.ref_new})
        self.command.invalidate_recordset()
        self.file.invalidate_recordset()

    def test_false_references_are_ignored(self):
        """Ignore malformed or non-Jinja references."""
        cmd_plain = self.Command.create(
            {
                "name": "Plain",
                "code": "print(test_version)",
                "variable_ids": [(6, 0, [self.variable_version.id])],
            }
        )
        cmd_bad = self.Command.create(
            {
                "name": "BadBrackets",
                "code": "{test_version}",
                "variable_ids": [(6, 0, [self.variable_version.id])],
            }
        )

        self._rename()
        cmd_plain.invalidate_recordset()
        cmd_bad.invalidate_recordset()

        self.assertEqual(cmd_plain.code, "print(test_version)")
        self.assertEqual(cmd_bad.code, "{test_version}")

    def test_multiple_occurrences_replace_all(self):
        """Replace all valid Jinja references in one field."""
        code = "A: {{ test_version }}, B: {{  test_version   }}, C-end"
        cmd_multi = self.Command.create(
            {
                "name": "Multi",
                "code": code,
                "variable_ids": [(6, 0, [self.variable_version.id])],
            }
        )

        self._rename()
        cmd_multi.invalidate_recordset()
        actual_ref = self.variable_version.reference
        expected = f"A: {{{{ {actual_ref} }}}}, " f"B: {{{{  {actual_ref}   }}}}, C-end"
        self.assertEqual(cmd_multi.code, expected)

    def test_template_files_updated(self):
        """Propagate rename in template and generated file."""
        tpl = self.env["cx.tower.file.template"].create(
            {
                "name": "TmpTpl",
                "file_name": "tpl.txt",
                "server_dir": "/tmp",
                "code": "{{ test_version }}",
                "variable_ids": [(6, 0, [self.variable_version.id])],
            }
        )
        tpl_file = self.File.create(
            {
                "name": "from_tpl.txt",
                "server_dir": "/tmp",
                "template_id": tpl.id,
                "code": "{{ test_version }}",
            }
        )

        self._rename()
        tpl.invalidate_recordset()
        tpl_file.invalidate_recordset()

        actual_ref = self.variable_version.reference
        expected = f"{{{{ {actual_ref} }}}}"
        self.assertEqual(tpl.code, expected)
        self.assertEqual(tpl_file.code, expected)

    def test_value_and_plan_line_update(self):
        """Update value_char and plan line condition."""

        def patched_mapping(_):
            return {
                "cx.tower.command": ["code", "path"],
                "cx.tower.file": ["code", "server_dir", "name"],
                "cx.tower.file.template": ["code", "server_dir", "file_name"],
                "cx.tower.variable.value": ["value_char"],
                "cx.tower.plan.line": ["condition"],
            }

        with patch.object(
            type(self.variable_version),
            "_get_propagation_field_mapping",
            patched_mapping,
        ):
            val = self.env["cx.tower.variable.value"].create(
                {
                    "variable_id": self.variable_version.id,
                    "value_char": "hello {{ test_version }} world",
                }
            )

            pl = self.plan_line_1
            pl.write(
                {
                    "variable_ids": [(6, 0, [self.variable_version.id])],
                    "condition": "if {{ test_version }} then",
                }
            )

            self.assertIn(self.variable_version.id, pl.variable_ids.ids)

            self._rename()
            val.invalidate_recordset()
            pl.invalidate_recordset()

            actual_ref = self.variable_version.reference
            expected_val = f"hello {{{{ {actual_ref} }}}} world"
            self.assertEqual(val.value_char, expected_val)
            expected_cond = f"if {{{{ {actual_ref} }}}} then"
            self.assertEqual(pl.condition, expected_cond)

    def test_variable_reference_update(self):
        """Test variable reference update cascades to dependent models"""
        # 1. Add a variable value to variable_os
        variable_value = self.VariableValue.create(
            {
                "variable_id": self.variable_os.id,
                "value_char": "Ubuntu 20.04",
                "server_id": self.server_test_1.id,
            }
        )

        # Store original references for comparison
        original_variable_reference = self.variable_os.reference
        original_variable_value_reference = variable_value.reference

        # 2. Change the reference for variable_os to "awesome_variable"
        self.variable_os.write({"reference": "awesome_variable"})

        # 3. Verify that references are updated for dependent models
        # Invalidate models to refresh all references
        self.env["cx.tower.variable"].invalidate_model(["reference"])
        self.env["cx.tower.variable.value"].invalidate_model(["reference"])

        # Check that variable reference was updated
        self.assertEqual(self.variable_os.reference, "awesome_variable")
        self.assertNotEqual(self.variable_os.reference, original_variable_reference)

        # Check that variable value reference was updated
        # to include the new variable reference
        self.assertIn("awesome_variable", variable_value.reference)
        self.assertNotEqual(variable_value.reference, original_variable_value_reference)

        # Verify the reference pattern for variable value follows the expected format:
        # <variable_reference>_<model_generic_reference>_<linked_model_generic_reference>_<linked_record_reference>  # noqa: E501
        expected_variable_pattern = (
            f"{self.variable_os.reference}_variable_value_server_"
            f"{self.server_test_1.reference}"
        )
        self.assertEqual(variable_value.reference, expected_variable_pattern)
