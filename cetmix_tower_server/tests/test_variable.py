from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo import _, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import Form
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
            expected_value = val[1] or ""
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

    def test_variable_value_access(self):
        """Test access rules for variable values"""
        server = self.server_test_1

        # Create variables with different access levels
        variable_private = self.Variable.create(
            {"name": "Private Variable", "access_level": "1"}
        )
        variable_private_value = self.VariableValue.create(
            {
                "variable_id": variable_private.id,
                "server_id": server.id,
                "value_char": "Private Value",
                "access_level": "1",
            }
        )

        variable_global = self.Variable.create(
            {"name": "Variable Global", "access_level": "1"}
        )
        variable_global_value = self.VariableValue.create(
            {
                "variable_id": variable_global.id,
                "is_global": True,
                "value_char": "Global Value",
                "access_level": "1",
            }
        )

        user_bob = self.user_bob

        # Ensure user_bob is not in any security groups initially
        self.remove_from_group(
            user_bob,
            [
                "cetmix_tower_server.group_user",
                "cetmix_tower_server.group_manager",
                "cetmix_tower_server.group_root",
            ],
        )

        # Add user_bob to group_user
        self.add_to_group(user_bob, "cetmix_tower_server.group_user")

        # Check access to private values for group_user without subscription
        self.assertFalse(
            self.VariableValue.with_user(user_bob).search(
                [("id", "=", variable_private_value.id)]
            ),
            "User must not see private variable values without subscription",
        )

        # Check that group_user cannot access global values (as per new logic)
        self.assertFalse(
            self.VariableValue.with_user(user_bob).search(
                [("id", "=", variable_global_value.id)]
            ),
            "User must not see global variable values",
        )

        # Subscribe user_bob to the server
        server.message_subscribe([user_bob.partner_id.id])

        # Check access to private values for subscribed users
        variable_private_value_as_bob = variable_private_value.with_user(user_bob)
        self.assertEqual(
            variable_private_value_as_bob.value_char,
            "Private Value",
            msg="User must be able to access private values after subscribing",
        )

        # Check that group_user still cannot access global values after subscription
        self.assertFalse(
            self.VariableValue.with_user(user_bob).search(
                [("id", "=", variable_global_value.id)]
            ),
            "User must not see global variable values",
        )

        # Add user_bob to group_manager
        self.add_to_group(user_bob, "cetmix_tower_server.group_manager")

        # Check that user_bob can create new variables with appropriate access levels
        variable_new_private_as_bob = self.Variable.with_user(user_bob).create(
            {"name": "New Private Variable", "access_level": "2"}
        )
        variable_vale_new_private_as_bob = self.VariableValue.with_user(
            user_bob
        ).create(
            {
                "variable_id": variable_new_private_as_bob.id,
                "server_id": server.id,
                "value_char": "New Private Value",
                "access_level": "2",
            }
        )
        self.assertEqual(
            variable_vale_new_private_as_bob.value_char,
            "New Private Value",
            msg="Manager must be able to create private variable values",
        )

        # Remove user_bob from group_manager before unsubscribing
        self.remove_from_group(user_bob, "cetmix_tower_server.group_manager")

        # Unsubscribe user from server and check access to private values
        server.message_unsubscribe([user_bob.partner_id.id])
        with self.assertRaises(AccessError):
            _ = variable_private_value_as_bob.value_char

        # Add user_bob to group_root
        self.add_to_group(user_bob, "cetmix_tower_server.group_root")

        # Check that root can see all variable values
        variable_private_value_as_bob = variable_private_value.with_user(user_bob)
        self.assertEqual(
            variable_private_value_as_bob.value_char,
            "Private Value",
            msg="Root must be able to access all private variable values",
        )
        variable_global_value_as_bob = variable_global_value.with_user(user_bob)
        self.assertEqual(
            variable_global_value_as_bob.value_char,
            "Global Value",
            msg="Root must be able to access all global variable values",
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
        with mute_logger("odoo.sql_db"), self.assertRaises(
            IntegrityError,
            msg="A variable value cannot be assigned multiple times to the same server",
        ):
            self.env["cx.tower.variable.value"].create(
                {
                    "variable_id": variable.id,
                    "value_char": "Production",
                    "server_id": server.id,
                }
            )

    def test_variable_access_rules(self):
        """Test access rules for `cx_tower_variable`."""
        # Create variables with different access levels
        variable_private = self.Variable.create(
            {"name": "Private Variable", "access_level": "1"}
        )
        variable_manager = self.Variable.create(
            {"name": "Manager Variable", "access_level": "2"}
        )
        variable_root = self.Variable.create(
            {"name": "Root Variable", "access_level": "3"}
        )

        # Attach variables to the server
        self.VariableValue.create(
            {
                "variable_id": variable_private.id,
                "server_id": self.server_test_1.id,
                "value_char": "Private Value",
                "access_level": "1",
            }
        )
        self.VariableValue.create(
            {
                "variable_id": variable_manager.id,
                "server_id": self.server_test_1.id,
                "value_char": "Manager Value",
                "access_level": "2",
            }
        )
        self.VariableValue.create(
            {
                "variable_id": variable_root.id,
                "server_id": self.server_test_1.id,
                "value_char": "Root Value",
                "access_level": "3",
            }
        )

        user_bob = self.user_bob
        # Remove the user from all groups and add to group_user
        self.remove_from_group(
            user_bob,
            ["cetmix_tower_server.group_manager", "cetmix_tower_server.group_root"],
        )
        self.add_to_group(user_bob, "cetmix_tower_server.group_user")

        # Verify the created variables and their access levels
        self.assertEqual(
            variable_private.access_level,
            "1",
            "Private variable must have access_level = 1",
        )
        self.assertEqual(
            variable_manager.access_level,
            "2",
            "Manager variable must have access_level = 2",
        )
        self.assertEqual(
            variable_root.access_level, "3", "Root variable must have access_level = 3"
        )

        # Check that user_bob sees only variables with access_level = 1
        variables_as_bob = self.Variable.with_user(user_bob).search([])
        self.assertIn(
            variable_private,
            variables_as_bob,
            f"User must see private variables. Available: {variables_as_bob.ids}",
        )
        self.assertNotIn(
            variable_manager,
            variables_as_bob,
            f"User must not see manager variables. Available: {variables_as_bob.ids}",
        )
        self.assertNotIn(
            variable_root,
            variables_as_bob,
            f"User must not see root variables. Available: {variables_as_bob.ids}",
        )

        # Add user to group_manager
        self.add_to_group(user_bob, "cetmix_tower_server.group_manager")
        variables_as_bob = self.Variable.with_user(user_bob).search([])
        self.assertIn(
            variable_manager,
            variables_as_bob,
            f"Manager must see manager variables. Available: {variables_as_bob.ids}",
        )
        self.assertNotIn(
            variable_root,
            variables_as_bob,
            f"Manager must not see root variables. Available: {variables_as_bob.ids}",
        )

        # Add user to group_root
        self.add_to_group(user_bob, "cetmix_tower_server.group_root")
        variables_as_bob = self.Variable.with_user(user_bob).search([])
        self.assertIn(
            variable_root,
            variables_as_bob,
            f"Root must see all variables. Available: {variables_as_bob.ids}",
        )

    def test_variable_value_access_rules(self):
        """Test access rules for `cx_tower_variable_value`."""
        server = self.server_test_1

        # Creating variables and their values
        variable_private = self.Variable.create(
            {"name": "Private Variable", "access_level": "1"}
        )
        variable_private_value = self.VariableValue.create(
            {
                "variable_id": variable_private.id,
                "server_id": server.id,
                "value_char": "Private Value",
                "access_level": "1",
            }
        )

        variable_global = self.Variable.create(
            {"name": "Global Variable", "access_level": "1"}
        )
        self.VariableValue.create(
            {
                "variable_id": variable_global.id,
                "is_global": True,
                "value_char": "Global Value",
                "access_level": "1",
            }
        )

        user_bob = self.user_bob
        # Remove the user from all groups and add to group_user
        self.remove_from_group(
            user_bob,
            ["cetmix_tower_server.group_manager", "cetmix_tower_server.group_root"],
        )
        self.add_to_group(user_bob, "cetmix_tower_server.group_user")

        # Subscribe the user to the server
        server.message_subscribe([user_bob.partner_id.id])
        variable_private_value_as_bob = variable_private_value.with_user(user_bob)
        self.assertEqual(
            variable_private_value_as_bob.value_char,
            "Private Value",
            "User must access private variable values",
        )

        # Checking the manager's rights
        self.add_to_group(user_bob, "cetmix_tower_server.group_manager")
        variable_private_value_as_bob = variable_private_value.with_user(user_bob)
        self.assertEqual(
            variable_private_value_as_bob.value_char,
            "Private Value",
            "Manager must access private variable values",
        )

        # Checking root rights
        self.add_to_group(user_bob, "cetmix_tower_server.group_root")
        variable_private_value_as_bob = variable_private_value.with_user(user_bob)
        self.assertEqual(
            variable_private_value_as_bob.value_char,
            "Private Value",
            "Root must access all variable values",
        )

    def test_variable_rendering_in_execution(self):
        """
        Test that all variables are used during
        execution regardless of access level.
        """
        server = self.server_test_1

        # Create variables with different access levels
        variable_user = self.Variable.create(
            {"name": "User Variable", "access_level": "1"}
        )
        variable_manager = self.Variable.create(
            {"name": "Manager Variable", "access_level": "2"}
        )
        variable_root = self.Variable.create(
            {"name": "Root Variable", "access_level": "3"}
        )

        # Creating variable values
        variable_user_value = self.VariableValue.create(
            {
                "variable_id": variable_user.id,
                "server_id": server.id,
                "value_char": "User Value",
                "access_level": variable_user.access_level,
            }
        )
        variable_manager_value = self.VariableValue.create(
            {
                "variable_id": variable_manager.id,
                "server_id": server.id,
                "value_char": "Manager Value",
                "access_level": variable_manager.access_level,
            }
        )
        variable_root_value = self.VariableValue.create(
            {
                "variable_id": variable_root.id,
                "server_id": server.id,
                "value_char": "Root Value",
                "access_level": variable_root.access_level,
            }
        )

        # Check the visibility of variables for User
        user_bob = self.user_bob
        self.remove_from_group(
            user_bob,
            ["cetmix_tower_server.group_manager", "cetmix_tower_server.group_root"],
        )
        self.add_to_group(user_bob, "cetmix_tower_server.group_user")

        # The user sees only User level variables
        variables_as_bob = self.Variable.with_user(user_bob).search([])
        self.assertIn(variable_user, variables_as_bob)
        self.assertNotIn(variable_manager, variables_as_bob)
        self.assertNotIn(variable_root, variables_as_bob)

        # Check the use of variables in the process
        # Emulate the execution of the command,
        # which must take into account all variables
        used_variables = {
            "User Variable": variable_user_value.value_char,
            "Manager Variable": variable_manager_value.value_char,
            "Root Variable": variable_root_value.value_char,
        }

        # Let's make sure that all variables have been used
        self.assertEqual(
            used_variables["User Variable"],
            "User Value",
            "User variable must be used during execution",
        )
        self.assertEqual(
            used_variables["Manager Variable"],
            "Manager Value",
            "Manager variable must be used during execution",
        )
        self.assertEqual(
            used_variables["Root Variable"],
            "Root Value",
            "Root variable must be used during execution",
        )

    def test_variable_access_levels(self):
        """Test that variables of all access levels are rendered correctly"""

        # Create variables with different access levels
        variable_user = self.Variable.create(
            {
                "name": "Directory2",
                "access_level": "1",  # User
            }
        )
        variable_manager = self.Variable.create(
            {
                "name": "Version2",
                "access_level": "2",  # Manager
            }
        )
        variable_root = self.Variable.create(
            {
                "name": "Revision2",
                "access_level": "3",  # Root
            }
        )

        # Create values for the variables
        server = self.server_test_1

        self.VariableValue.create(
            {
                "variable_id": variable_user.id,
                "server_id": server.id,
                "value_char": "User Value",
                "access_level": variable_user.access_level,
            }
        )
        self.VariableValue.create(
            {
                "variable_id": variable_manager.id,
                "server_id": server.id,
                "value_char": "Manager Value",
                "access_level": variable_manager.access_level,
            }
        )
        self.VariableValue.create(
            {
                "variable_id": variable_root.id,
                "is_global": True,
                "value_char": "Root Value",
                "access_level": variable_root.access_level,
            }
        )

        # Create a command using variables in path and code
        command = self.Command.create(
            {
                "name": "Test Command",
                "path": "{{ directory2 }}/{{ version2 }}",
                "code": "print('{{ version2 }} {{ revision2 }}')",
                "server_ids": [(4, server.id)],
                "access_level": "1",
            }
        )

        # Create a file using variables in name, directory, and code
        file = self.File.create(
            {
                "name": "{{ version2 }}.txt",
                "server_dir": "{{ revision2 }}",
                "code": "Variables: {{ directory2 }}, {{ version2 }}, {{ revision2 }}",
                "server_id": server.id,
            }
        )

        # Assign user to "Tower/Users" group
        user = self.user_bob
        self.remove_from_group(
            user,
            [
                "cetmix_tower_server.group_manager",
                "cetmix_tower_server.group_root",
            ],
        )
        self.add_to_group(user, "cetmix_tower_server.group_user")

        # Checking the rendering of the command on behalf of the user
        command_as_user = command.with_user(user)
        with self.assertRaises(
            AccessError
        ):  # Verify that access is denied without subscription
            command_as_user.read([])

        # Signing the user to the server
        server.message_subscribe([user.partner_id.id])

        # Make sure the command is available after subscribing
        rendered_command = server._render_command(command_as_user)

        self.assertEqual(
            rendered_command["rendered_path"],
            "User Value/Manager Value",
            "Command path must render all variables correctly",
        )
        self.assertEqual(
            rendered_command["rendered_code"],
            "print('Manager Value Root Value')",
            "Command code must render all variables correctly",
        )

        # Render file fields manually
        file_as_user = file.with_user(user)
        rendered_file_name = file_as_user.name.replace(
            "{{ version2 }}", "Manager Value"
        )
        rendered_file_directory = file_as_user.server_dir.replace(
            "{{ revision2 }}", "Root Value"
        )
        rendered_file_code = (
            file_as_user.code.replace("{{ directory2 }}", "User Value")
            .replace("{{ version2 }}", "Manager Value")
            .replace("{{ revision2 }}", "Root Value")
        )

        # Verify file rendering
        self.assertEqual(
            rendered_file_name,
            "Manager Value.txt",
            "File name must render all variables correctly",
        )
        self.assertEqual(
            rendered_file_directory,
            "Root Value",
            "File directory must render all variables correctly",
        )
        self.assertEqual(
            rendered_file_code,
            "Variables: User Value, Manager Value, Root Value",
            "File code must render all variables correctly",
        )

    def test_variable_value_access_level_update(self):
        """
        Test that when the access level of a variable is updated in code,
        all related variable values are also updated accordingly.
        """
        # Create a variable with access level "Manager"
        variable = self.Variable.create({"name": "Test Variable", "access_level": "2"})

        # Create the value of the variable on the server
        variable_value = self.VariableValue.create(
            {
                "variable_id": variable.id,
                "server_id": self.server_test_1.id,
                "value_char": "Test Value",
            }
        )

        # Check that the access level of the value matches the variable
        self.assertEqual(
            variable_value.access_level,
            variable.access_level,
            "Initial access level of variable value must match the variable",
        )

        # Update the access level of the variable through the code
        variable.write({"access_level": "1"})

        # Rereading the variable value object
        variable_value.invalidate_cache()

        # Check that the access level of the value has also been updated
        self.assertEqual(
            variable_value.access_level,
            "1",
            "Access level of variable value must be updated "
            "when variable's access level changes",
        )

        # Let's try to increase the access level
        # of the variable again through the code
        variable.write({"access_level": "3"})

        # Re-reading the object
        variable_value.invalidate_cache()

        # Check that the change is reflected in the value of
        self.assertEqual(
            variable_value.access_level,
            "3",
            "Access level of variable value must update to "
            "reflect the variable's access level",
        )

        # Check that it is impossible to set the level lower
        # than that of the variable (we will get an error)
        with self.assertRaises(ValidationError):
            variable_value.write({"access_level": "1"})
