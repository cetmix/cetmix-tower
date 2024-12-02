from .common import TestTowerCommon


class TestTowerServerTemplate(TestTowerCommon):
    def test_create_server_from_template(self):
        """
        Create new server from template
        """
        self.assertFalse(
            self.Server.search(
                [("server_template_id", "=", self.server_template_sample.id)]
            ),
            "The servers shouldn't exist",
        )
        # add variable values to server template
        self.VariableValue.create(
            {
                "variable_id": self.variable_version.id,
                "server_template_id": self.server_template_sample.id,
                "value_char": "test",
            }
        )

        # add server logs to template
        command_for_log = self.Command.create(
            {"name": "Get system info", "code": "uname -a"}
        )

        server_template_log = self.ServerLog.create(
            {
                "name": "Log from server template",
                "server_template_id": self.server_template_sample.id,
                "log_type": "command",
                "command_id": command_for_log.id,
            }
        )

        self.assertEqual(
            len(self.variable_version.value_ids),
            1,
            "The variable must have one value only",
        )

        server_log = self.ServerLog.search([("command_id", "=", command_for_log.id)])
        self.assertEqual(len(server_log), 1, "Server log must be one")

        # create new server from template
        new_server = self.ServerTemplate.create_server_from_template(
            self.server_template_sample.reference,
            "server_from_template",
            ip_v4_address="0.0.0.0",
        )

        server = self.Server.search(
            [("server_template_id", "=", self.server_template_sample.id)]
        )
        self.assertEqual(new_server, server, "Servers must be the same")
        self.assertEqual(
            new_server.name,
            "server_from_template",
            "Server name must be server_from_template",
        )
        self.assertEqual(
            new_server.ip_v4_address, "0.0.0.0", "Server IP must be 0.0.0.0"
        )
        self.assertEqual(
            new_server.os_id, self.os_debian_10, "Server os must be Debian"
        )
        self.assertEqual(new_server.ssh_port, "22", "Server SSH Port must be 22")
        self.assertEqual(
            new_server.ssh_username, "admin", "Server SSH Username must be 'admin'"
        )
        self.assertEqual(
            new_server.ssh_password,
            "password",
            "Server SSH Password must be 'password'",
        )
        self.assertEqual(
            new_server.ssh_auth_mode, "p", "Server SSH Auth Mode must be 'p'"
        )
        self.assertEqual(
            len(self.variable_version.value_ids),
            2,
            "The variable must have two value only",
        )

        server_log = self.ServerLog.search([("command_id", "=", command_for_log.id)])
        self.assertEqual(len(server_log), 2, "Server log must be two")

        server_log = server_log.filtered(lambda rec: rec.server_id == new_server)
        self.assertNotEqual(server_log, server_template_log)

    def test_create_server_from_template_wizard(self):
        """
        Create new server from template from wizard
        """
        action = self.server_template_sample.action_create_server()
        wizard = (
            self.env["cx.tower.server.template.create.wizard"]
            .with_context(**action["context"])
            .new({})
        )
        self.assertEqual(
            self.server_template_sample,
            wizard.server_template_id,
            "Server Templates must be the same",
        )

        self.assertFalse(
            self.Server.search(
                [("server_template_id", "=", self.server_template_sample.id)]
            ),
            "The servers shouldn't exist",
        )

        wizard.update(
            {
                "name": "test",
                "ip_v4_address": "0.0.0.0",
            }
        )
        action = wizard.action_confirm()

        server = self.Server.search(
            [("server_template_id", "=", self.server_template_sample.id)]
        )
        self.assertEqual(action["res_id"], server.id, "Server ids must be the same")

    def test_create_server_from_template_action(self):
        """
        Create new server from action
        """
        name = "server from template"
        self.assertFalse(
            self.Server.search([("name", "=", name)]),
            "Server should not exist",
        )
        # add variable values to server template
        self.VariableValue.create(
            {
                "variable_id": self.variable_version.id,
                "server_template_id": self.server_template_sample.id,
                "value_char": "test template version",
            }
        )
        self.VariableValue.create(
            {
                "variable_id": self.variable_url.id,
                "server_template_id": self.server_template_sample.id,
                "value_char": "test template url",
            }
        )

        # create new server with new variable
        self.ServerTemplate.create_server_from_template(
            self.server_template_sample.reference,
            "server from template",
            ip_v4_address="localhost",
            ssh_username="test",
            ssh_password="test",
            configuration_variables={
                self.variable_version.reference: "test server version",
                "new_variable": "new_value",
            },
        )
        new_server = self.Server.search([("name", "=", name)])

        self.assertTrue(new_server, "Server must exist!")
        self.assertEqual(
            len(new_server.variable_value_ids), 3, "Should be 3 variable values!"
        )

        # check variable values
        var_version_value = new_server.variable_value_ids.filtered(
            lambda rec: rec.variable_id == self.variable_version
        )
        self.assertEqual(
            var_version_value.value_char,
            "test server version",
            "Version variable values should be with new values for "
            "server from template",
        )

        var_url_value = new_server.variable_value_ids.filtered(
            lambda rec: rec.variable_id == self.variable_url
        )
        self.assertEqual(
            var_url_value.value_char,
            "test template url",
            "Url variable values should be same as in the template",
        )

        var_new_value = new_server.variable_value_ids.filtered(
            lambda rec: rec.variable_id.reference == "new_variable"
        )
        self.assertTrue(var_new_value, "New variable should exist on the server")
        self.assertEqual(
            var_new_value.value_char,
            "new_value",
            "New variable values should be 'new_values'",
        )

    def test_server_template_copy(self):
        """
        Test duplicating a Server Template with variable values and server logs
        """

        # A server template
        server_template = self.server_template_sample

        # Add variable values to the server template
        original_variable_value = self.VariableValue.create(
            {
                "variable_id": self.variable_version.id,
                "server_template_id": server_template.id,
                "value_char": "test",
            }
        )

        # Create a command for the server log
        command_for_log = self.Command.create(
            {
                "name": "Get system info",
                "code": "uname -a",
            }
        )

        # Add server logs to the template
        original_log = self.ServerLog.create(
            {
                "name": "Log from server template",
                "server_template_id": server_template.id,
                "log_type": "command",
                "command_id": command_for_log.id,
            }
        )

        # Duplicate the server template
        copied_template = server_template.copy()

        # Ensure the new server template was created with a new ID
        self.assertNotEqual(
            copied_template.id,
            server_template.id,
            "Copied server template should have a different ID from the original",
        )

        # Check that the copied template has the same number of variable values
        self.assertEqual(
            len(copied_template.variable_value_ids),
            len(server_template.variable_value_ids),
            (
                "Copied template should have the same "
                "number of variable values as the original"
            ),
        )

        # Ensure the variable itself was copied (check variable_id)
        copied_variable_value = copied_template.variable_value_ids
        self.assertEqual(
            copied_variable_value.variable_id.id,
            original_variable_value.variable_id.id,
            "Variable ID should be the same in the copied template",
        )
        self.assertEqual(
            copied_variable_value.value_char,
            original_variable_value.value_char,
            "Variable value should be the same in the copied template",
        )

        # Check that the copied template has the same number of server logs
        self.assertEqual(
            len(copied_template.server_log_ids),
            len(server_template.server_log_ids),
            (
                "Copied template should have the same "
                "number of server logs as the original"
            ),
        )

        # Ensure the first server log in the copied template matches the original
        copied_log = copied_template.server_log_ids
        self.assertEqual(
            copied_log.name,
            original_log.name,
            "Server log name should be the same in the copied template",
        )
        self.assertEqual(
            copied_log.command_id.id,
            original_log.command_id.id,
            "Command ID should be the same in the copied server log",
        )
        self.assertEqual(
            copied_log.command_id.code,
            original_log.command_id.code,
            "Command code should be the same in the copied server log",
        )

    def test_required_flag_in_create_server_wizard(self):
        """
        Test that the 'Required' flag is correctly passed from the Server Template
        to the New Server Wizard.
        """
        # Set the required flag for a variable
        self.VariableValue.create(
            {
                "variable_id": self.variable_version.id,
                "server_template_id": self.server_template_sample.id,
                "value_char": "Test Value",
                "required": True,
            }
        )

        # Open the server creation wizard
        action = self.server_template_sample.action_create_server()
        wizard_context = action.get("context", {})
        default_line_ids = wizard_context.get("default_line_ids", [])

        # We check that required is passed to the wizard
        self.assertTrue(
            any(line[2].get("required") for line in default_line_ids),
            "The 'Required' flag should be correctly passed to the wizard.",
        )

    def test_required_attribute_in_wizard_field(self):
        """
        Test that the 'required' attribute
        is correctly applied to the 'value_char' field
        in the wizard when the variable is marked as required.
        """
        # Create a required variable
        self.VariableValue.create(
            {
                "variable_id": self.variable_version.id,
                "server_template_id": self.server_template_sample.id,
                "value_char": "Test Value",
                "required": True,
            }
        )

        # Open the wizard
        wizard = self.env["cx.tower.server.template.create.wizard"].create(
            {
                "server_template_id": self.server_template_sample.id,
                "name": "Test Server",
                "ssh_username": "admin",
            }
        )

        # Checking that the 'required' flag is passed to the form context
        required_fields = [
            line.required
            for line in wizard.line_ids
            if line.variable_id == self.variable_version
        ]
        self.assertTrue(
            all(required_fields),
            "The 'required' attribute should be correctly "
            "applied to the 'value_char' field for required variables.",
        )

    def test_successful_server_creation_with_required_variables(self):
        """
        Test that a server is successfully created
        when all required variables are filled in the wizard.
        """
        # Adding a required variable
        self.VariableValue.create(
            {
                "variable_id": self.variable_version.id,
                "server_template_id": self.server_template_sample.id,
                "value_char": "",
                "required": True,
            }
        )

        # Open the wizard and fill in the data
        wizard = self.env["cx.tower.server.template.create.wizard"].create(
            {
                "server_template_id": self.server_template_sample.id,
                "name": "Test Server With Required Variables",
                "ssh_username": "admin",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "variable_id": self.variable_version.id,
                            "value_char": "Test Value",
                            "required": True,
                        },
                    )
                ],
            }
        )

        # Checking the successful creation of the server
        action = wizard.action_confirm()
        self.assertTrue(action, "Server should be created successfully.")

        # Checking that the server has been created
        server = self.Server.search(
            [
                ("name", "=", "Test Server With Required Variables"),
                ("server_template_id", "=", self.server_template_sample.id),
            ]
        )
        self.assertTrue(server, "Server should exist.")
        self.assertEqual(
            server.variable_value_ids.filtered(
                lambda v: v.variable_id == self.variable_version
            ).value_char,
            "Test Value",
            "The variable value should be saved correctly.",
        )

    def test_optional_variable_with_empty_value(self):
        """
        Test that an optional variable
        with an empty value is saved correctly
        in the wizard and does not block server creation.
        """
        # Adding an optional variable
        self.VariableValue.create(
            {
                "variable_id": self.variable_url.id,
                "server_template_id": self.server_template_sample.id,
                "value_char": "",
                "required": False,
            }
        )

        # Open the wizard
        wizard = self.env["cx.tower.server.template.create.wizard"].create(
            {
                "server_template_id": self.server_template_sample.id,
                "name": "Server With Optional Variable",
                "ssh_username": "admin",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "variable_id": self.variable_url.id,
                            "value_char": "",
                            "required": False,
                        },
                    )
                ],
            }
        )

        # Checking that the wizard is saved without errors
        wizard.action_confirm()

        # Checking that the server has been created
        server = self.Server.search(
            [
                ("name", "=", "Server With Optional Variable"),
                ("server_template_id", "=", self.server_template_sample.id),
            ]
        )
        self.assertTrue(
            server, "Server should be created successfully with optional variables."
        )

        # Checking that an optional variable is saved with an empty value
        variable = server.variable_value_ids.filtered(
            lambda v: v.variable_id == self.variable_url
        )
        self.assertTrue(variable, "Optional variable should be attached to the server.")
        self.assertEqual(
            variable.value_char, "", "Optional variable should have an empty value."
        )

    def test_wizard_without_variables(self):
        """
        Test that the wizard does not display
        any variables if the server template has none.
        """
        # Removing all variables from the template
        self.VariableValue.search(
            [("server_template_id", "=", self.server_template_sample.id)]
        ).unlink()

        # Open the wizard
        wizard = self.env["cx.tower.server.template.create.wizard"].create(
            {
                "server_template_id": self.server_template_sample.id,
                "name": "Server Without Variables",
                "ssh_username": "admin",
            }
        )

        # Checking that the wizard does not contain variables
        self.assertFalse(wizard.line_ids, "Wizard should not display any variables.")

    def test_update_required_variable_value(self):
        """
        Test that the value of a required variable
        can be updated in the wizard and saved correctly.
        """
        # Adding a required variable
        self.VariableValue.create(
            {
                "variable_id": self.variable_version.id,
                "server_template_id": self.server_template_sample.id,
                "value_char": "Old Value",
                "required": True,
            }
        )

        # Open the wizard and update the variable value
        wizard = self.env["cx.tower.server.template.create.wizard"].create(
            {
                "server_template_id": self.server_template_sample.id,
                "name": "Server With Updated Variable",
                "ssh_username": "admin",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "variable_id": self.variable_version.id,
                            "value_char": "New Value",
                            "required": True,
                        },
                    )
                ],
            }
        )
        wizard.action_confirm()

        # Checking that the variable value has been updated
        server = self.Server.search([("name", "=", "Server With Updated Variable")])
        variable = server.variable_value_ids.filtered(
            lambda v: v.variable_id == self.variable_version
        )
        self.assertEqual(
            variable.value_char,
            "New Value",
            "The variable value should be updated correctly.",
        )

    def test_optional_variable_handling(self):
        """
        Test that optional variables do not block server creation,
        even if their values are empty or missing.
        """
        # Adding an optional variable to the template
        self.VariableValue.create(
            {
                "variable_id": self.variable_url.id,
                "server_template_id": self.server_template_sample.id,
                "value_char": "",
                "required": False,
            }
        )

        # Specify an optional variable with an empty value
        values = self.server_template_sample._prepare_server_values(
            configuration_variables={self.variable_url.reference: ""}
        )

        # Checking that the optional variable is processed correctly
        variable_data = next(
            (
                v
                for v in values[0]["variable_value_ids"]
                if v[2]["variable_id"] == self.variable_url.id
            ),
            None,
        )
        self.assertIsNotNone(
            variable_data,
            "The optional variable should be included "
            "in the server values even if empty.",
        )
        self.assertEqual(
            variable_data[2]["value_char"],
            "",
            "Optional variable should have an empty value.",
        )
