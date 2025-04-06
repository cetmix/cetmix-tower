from .common import TestTowerCommon


class TestUpdateRelatedVariableNames(TestTowerCommon):
    """Test Update Related Variable Names"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create test variables
        cls.var1 = cls.Variable.create({"name": "var1", "reference": "var1"})
        cls.var2 = cls.Variable.create({"name": "var2", "reference": "var2"})
        cls.var3 = cls.Variable.create({"name": "var3", "reference": "var3"})

        cls.test_command = cls.Command.create(
            {
                "name": "Test Command",
                "code": "{{ var1 }} and {{ var2 }}",
                "path": "{{ var3 }}",
            }
        )

        cls.server = cls.Server.create(
            {
                "name": "Test Server",
                "color": 2,
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "k",
                "ssh_key_id": cls.key_1.id,
            }
        )
        cls.test_file = cls.File.create(
            {
                "server_id": cls.server.id,
                "code": "{{ var1 }} is used",
                "server_dir": "path/to/{{ var2 }}",
                "name": "{{ var3 }}.txt",
            }
        )

        cls.test_plan_line = cls.plan_line.create(
            {
                "command_id": cls.test_command.id,
                "condition": "Condition with {{ var1 }} and {{ var2 }}",
            }
        )

        cls.test_variable_value = cls.VariableValue.create(
            {
                "variable_id": cls.variable_os.id,
                "value_char": "{{ var1 }} is here and {{ var2 }} too",
            }
        )

        cls.test_file_template = cls.FileTemplate.create(
            {
                "name": "Test File Template",
                "code": "{{ var1 }} in code",
                "server_dir": "This path has {{ var2 }}",
                "file_name": "file_name_with_{{ var1 }}",
            }
        )

    def test_variables_command_computation(self):
        """
        Test that the variable_ids field is correctly computed based on the 'code'
        and 'path' fields of the command.
        """
        # Verify that the correct variables are assigned to variable_ids
        self.assertEqual(
            set(self.test_command.variable_ids.ids),
            {self.var1.id, self.var2.id, self.var3.id},
            "The variable_ids should contain var1, var2, and var3.",
        )

    def test_variables_command_clearing(self):
        """
        Test that the variable_ids field is cleared when
        no variables are found in the code or path.
        """
        # Update code and path to remove references
        self.test_command.write(
            {"code": "No variables here", "path": "No variables here either"}
        )
        # Verify that variable_ids is empty
        self.assertFalse(
            self.test_command.variable_ids,
            "The variable_ids should be empty when no variables are found.",
        )

    def test_variables_file_computation(self):
        """
        Test that the variable_ids field is correctly computed based on the 'code',
        'server_dir', and 'name' fields of the file.
        """
        # Verify that the correct variables are assigned to variable_ids
        self.assertEqual(
            set(self.test_file.variable_ids.ids),
            {self.var1.id, self.var2.id, self.var3.id},
            "The variable_ids should contain var1, var2, and var3.",
        )

    def test_variables_file_clearing(self):
        """
        Test that the variable_ids field is cleared when
        no variables are found in the code, server_dir, or name fields.
        """
        # Update the file to remove references
        self.test_file.write(
            {
                "code": "No variables here",
                "server_dir": "No variables here either",
                "name": "no_var.txt",
            }
        )
        # Verify that variable_ids is empty
        self.assertFalse(
            self.test_file.variable_ids,
            "The variable_ids should be empty when no variables are found.",
        )

    def test_variables_plan_line_computation(self):
        """
        Test that the variable_ids field is correctly
        computed based on the 'condition' field of the plan line.
        """
        # Verify that the correct variables are assigned to variable_ids
        self.assertEqual(
            set(self.test_plan_line.variable_ids.ids),
            {self.var1.id, self.var2.id},
            "The variable_ids should contain var1 and var2.",
        )

    def test_variables_plan_line_clearing(self):
        """
        Test that the variable_ids field is cleared when
        no variables are found in the condition field.
        """
        # Update the plan line to remove references
        self.test_plan_line.write({"condition": "No variables in this condition"})
        # Verify that variable_ids is empty
        self.assertFalse(
            self.test_plan_line.variable_ids,
            "The variable_ids should be empty when no variables are found.",
        )

    def test_variables_variable_value_computation(self):
        """
        Test that the variable_ids field is correctly
        computed based on the 'value_char' field.
        """
        # Verify that the correct variables are assigned to variable_ids
        self.assertEqual(
            set(self.test_variable_value.variable_ids.ids),
            {self.var1.id, self.var2.id},
            "The variable_ids should contain var1 and var2.",
        )

    def test_variables_variable_value_clearing(self):
        """
        Test that the variable_ids field is cleared when
        no variables are found in the value_char field.
        """
        # Update the variable value to remove references
        self.test_variable_value.write({"value_char": "No variables in this text"})
        # Verify that variable_ids is empty
        self.assertFalse(
            self.test_variable_value.variable_ids,
            "The variable_ids should be empty when no variables are found.",
        )

    def test_variables_file_template_computation(self):
        """
        Test that the variable_ids field is correctly computed
        based on 'code', 'server_dir', and 'file_name' fields.
        """
        # Verify that the correct variables are assigned to variable_ids
        self.assertEqual(
            set(self.test_file_template.variable_ids.ids),
            {self.var1.id, self.var2.id},
            "The variable_ids should contain var1 and var2.",
        )

    def test_variable_file_template_clearing(self):
        """
        Test that the variable_ids field is cleared when
        no variables are found in code, server_dir, or file_name.
        """
        # Update the file template to remove references
        self.test_file_template.write(
            {
                "code": "No variables here",
                "server_dir": "No variables here either",
                "file_name": "no_var_in_file",
            }
        )
        # Verify that variable_ids is empty
        self.assertFalse(
            self.test_file_template.variable_ids,
            "The variable_ids should be empty when no variables are found.",
        )
