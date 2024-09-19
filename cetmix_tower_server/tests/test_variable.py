from unittest.mock import patch

from odoo import _, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import Form

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
            variable_records = self.VariableValues.search([("is_global", "=", True)])
        len_vals = len(vals)

        # Ensure correct number of records
        self.assertEqual(
            len(variable_records), len_vals, msg="Must be %s records" % str(len_vals)
        )

        # Check variable values
        for val in vals:
            variable_line = variable_records.filtered(
                lambda v, val=val: v.variable_id.id == val[0]
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
            f.save()

        vals = [(self.variable_os.id, "Debian"), (self.variable_version.id, "10.0")]
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
                line.value_char = "{{ test_dir }}/{{ test_version }}"
            with f.variable_value_ids.new() as line:
                line.variable_id = self.variable_url
                line.value_char = "{{ test_path_ }}/example.com"
            f.save()

        # Create a global value for the 'Version' variable
        self.VariableValues.create(
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

    def test_variable_value_toggle_global(self):
        """Test what happens when variable value 'global' setting is togged"""

        variable_meme = self.Variable.create({"name": "meme"})
        variable_value_pepe = self.VariableValues.create(
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
            self.VariableValues.create(
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

    def test_variable_value_access(self):
        """Test access rules for variable values"""
        server = self.server_test_1

        # Create variables assigned to server
        # Private
        variable_private = self.Variable.create({"name": "Private Variable"})
        variable_private_value = self.VariableValues.create(
            {
                "variable_id": variable_private.id,
                "server_id": server.id,
                "value_char": "Private Value",
            }
        )

        # Global
        variable_global = self.Variable.create({"name": "Variable Global"})
        variable_global_value = self.VariableValues.create(
            {
                "variable_id": variable_global.id,
                "is_global": True,
                "value_char": "Global Value",
            }
        )

        user_bob = self.user_bob

        # Remove user_bob from all tower security groups for sure
        self.remove_from_group(
            user_bob,
            [
                "cetmix_tower_server.group_user",
                "cetmix_tower_server.group_manager",
                "cetmix_tower_server.group_root",
            ],
        )

        # Make user_bob member of a group_user
        self.add_to_group(user_bob, "cetmix_tower_server.group_user")

        # Check if group_user member can access global values
        variable_global_value_as_bob = variable_global_value.with_user(user_bob)
        variable_global_value = variable_global_value_as_bob.value_char
        self.assertEqual(
            variable_global_value, "Global Value", msg="Must return 'Global Value'"
        )
        # Check what group_user member can't access values of variables
        #  of servers that he doesn't follow
        variable_private_value_as_bob = variable_private_value.with_user(user_bob)
        with self.assertRaises(AccessError):
            variable_private_value = variable_private_value_as_bob.value_char

        # Make user_bob follower of server created
        server.message_subscribe([user_bob.partner_id.id])

        # Check if he has access to values of variables of servers that he follows
        variable_private_value = variable_private_value_as_bob.value_char

        self.assertEqual(variable_private_value, "Private Value")

        # Check that user_bob can't create new variable values
        with self.assertRaises(AccessError):
            self.VariableValues.with_user(user_bob).create(
                {
                    "variable_id": variable_private.id,
                    "server_id": server.id,
                    "value_char": "Private Value 1",
                }
            )

        # Make user_bob member of a group_manager
        self.add_to_group(user_bob, "cetmix_tower_server.group_manager")

        # Check that user_bob can create new variables either global and local
        variable_new_global_as_bob = self.Variable.with_user(user_bob).create(
            {"name": "New Global Variable"}
        )
        variable_new_global_value_as_bob = self.VariableValues.with_user(
            user_bob
        ).create(
            {
                "variable_id": variable_new_global_as_bob.id,
                "is_global": True,
                "value_char": "Global Value 1",
            }
        )
        self.assertEqual(
            variable_new_global_value_as_bob.value_char,
            "Global Value 1",
            "Must return Global Value 1",
        )

        variable_new_private_as_bob = self.Variable.with_user(user_bob).create(
            {"name": "New Private Variable"}
        )
        variable_vale_new_private_as_bob = self.VariableValues.with_user(
            user_bob
        ).create(
            {
                "variable_id": variable_new_private_as_bob.id,
                "server_id": server.id,
                "value_char": "New Private Value",
            }
        )
        self.assertEqual(
            variable_vale_new_private_as_bob.value_char,
            "New Private Value",
            "Must return New Private Value",
        )

        # Remove user from followers of the server, check if he lost access to private
        # variables

        server.message_unsubscribe([user_bob.partner_id.id])
        with self.assertRaises(AccessError):
            variable_private_value = variable_private_value_as_bob.value_char

        # Make user_bob member of group_root
        self.add_to_group(user_bob, "cetmix_tower_server.group_root")

        # Check if he can see all variables
        self.assertEqual(
            variable_vale_new_private_as_bob.value_char, "New Private Value"
        )
        self.assertEqual(variable_new_global_value_as_bob.value_char, "Global Value 1")

    def test_system_variable_server_type_values(self):
        """Test system variables of `server` type"""

        # Modify server record for testing
        self.server_test_1.ip_v6_address = "suchmuchipv6"
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
                " {{ tower.server.ipv6 }} ",
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
