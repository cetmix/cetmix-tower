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
        self.VariableValues.create(
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
        self.VariableValues.create(
            {
                "variable_id": self.variable_version.id,
                "server_template_id": self.server_template_sample.id,
                "value_char": "test template version",
            }
        )
        self.VariableValues.create(
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
        self.VariableValues.create(
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
        self.ServerLog.create(
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

        # Ensure the first variable value in the copied template matches the original
        original_variable_value = server_template.variable_value_ids
        copied_variable_value = copied_template.variable_value_ids

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
        original_log = server_template.server_log_ids
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
