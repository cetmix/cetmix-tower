import base64

from odoo import _
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase


class TestTowerYamlImportWizUpload(TransactionCase):
    """Test Tower YAML Import Wizard Upload"""

    def setUp(self):
        super().setUp()

        # Variables
        self.Variable = self.env["cx.tower.variable"]
        self.variable_yaml_test = self.Variable.create(
            {"name": "YAML Test", "reference": "yaml_test"}
        )
        self.variable_yaml_url = self.Variable.create(
            {"name": "YAML URL", "reference": "yaml_url"}
        )

        # Tags
        self.Tag = self.env["cx.tower.tag"]
        self.tag_yaml_test = self.Tag.create(
            {"name": "YAML Test", "reference": "yaml_test"}
        )
        self.tag_another_yaml_test = self.Tag.create(
            {"name": "Another YAML Test", "reference": "another_yaml_test"}
        )

        # Commands
        self.Command = self.env["cx.tower.command"]
        self.command_yaml_test = self.Command.create(
            {"name": "Test Yaml Command", "reference": "test_yaml_command"}
        )

        # Flight Plan
        self.FlightPlan = self.env["cx.tower.plan"]
        self.flight_plan_yaml_test = self.FlightPlan.create(
            {
                "name": "Test Yaml Flight Plan",
                "reference": "test_yaml_flight_plan",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "condition": False,
                            "use_sudo": False,
                            "command_id": self.command_yaml_test.id,
                        },
                    ),
                ],
            }
        )

        # Create Server Template used for testing
        self.server_template_yaml_test = self.env["cx.tower.server.template"].create(
            {
                "name": "Test Server Template",
                "tag_ids": [
                    (4, self.tag_yaml_test.id),
                    (4, self.tag_another_yaml_test.id),
                ],
                "variable_value_ids": [
                    (
                        0,
                        0,
                        {
                            "variable_id": self.variable_yaml_test.id,
                            "value_char": "Some Test Value",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "variable_id": self.variable_yaml_url.id,
                            "value_char": "https://cetmix.com",
                        },
                    ),
                ],
                "flight_plan_id": self.flight_plan_yaml_test.id,
            }
        )

        # Server Logs
        self.ServerLog = self.env["cx.tower.server.log"]
        self.server_log_yaml_test = self.ServerLog.create(
            {
                "name": "Test Server Log",
                "reference": "test_server_log",
                "command_id": self.command_yaml_test.id,
                "log_type": "command",
                "server_template_id": self.server_template_yaml_test.id,
            }
        )

        # YAML code
        self.yaml_code = self.server_template_yaml_test.with_context(
            explode_related_record=True
        ).yaml_code
        self.yaml_file = base64.b64encode(self.yaml_code.encode("utf-8"))

        # YAML import upload wizard
        self.YamlImportWizUpload = self.env["cx.tower.yaml.import.wiz.upload"]
        self.yaml_upload_wizard = self.YamlImportWizUpload.create(
            {"yaml_file": self.yaml_file, "file_name": "test_yaml_file.yaml"}
        )

        # YAML import wizard
        self.import_wizard_action = self.yaml_upload_wizard.action_import_yaml()
        self.import_wizard = self.env[self.import_wizard_action["res_model"]].browse(
            self.import_wizard_action["res_id"]
        )

    def test_extract_yaml_data(self):
        """Test extract YAML data from file"""

        # -- 1 --
        # Test if YAML file is valid
        extracted_yaml_data = self.yaml_upload_wizard._extract_yaml_data()
        self.assertEqual(
            extracted_yaml_data[0],
            self.yaml_code,
            "YAML code is not extracted correctly",
        )
        self.assertEqual(
            extracted_yaml_data[1],
            "cx.tower.server.template",
            "Model name is not extracted correctly",
        )
        self.assertEqual(
            extracted_yaml_data[2],
            self.server_template_yaml_test.id,
            "Record ID is not extracted correctly",
        )

        # -- 2 --
        # Test if invalid model is handled properly
        # Replace model name with invalid model
        self.invalid_yaml_code = self.yaml_code.replace(
            "server_template", "invalid_model"
        )
        self.invalid_yaml_file = base64.b64encode(
            self.invalid_yaml_code.encode("utf-8")
        )
        self.yaml_upload_wizard.yaml_file = self.invalid_yaml_file
        with self.assertRaises(ValidationError) as e:
            self.yaml_upload_wizard._extract_yaml_data()
        self.assertEqual(
            e.exception.name,
            _("Invalid model specified in the YAML file"),
            "Exception message does not match",
        )

        # -- 3 --
        # Test if non YAML supported model is handled properly
        # Replace model name with non YAML supported model
        self.non_yaml_supported_yaml_code = self.yaml_code.replace(
            "server_template", "server"
        )
        self.non_yaml_supported_yaml_file = base64.b64encode(
            self.non_yaml_supported_yaml_code.encode("utf-8")
        )
        self.yaml_upload_wizard.yaml_file = self.non_yaml_supported_yaml_file
        with self.assertRaises(ValidationError) as e:
            self.yaml_upload_wizard._extract_yaml_data()
        self.assertEqual(
            e.exception.name,
            _("Model does not support YAML import"),
            "Exception message does not match",
        )

        # -- 4 --
        # Test if YAML that is not a dictionary is handled properly
        self.invalid_yaml_file = base64.b64encode(b"Invalid YAML file")
        self.yaml_upload_wizard.yaml_file = self.invalid_yaml_file
        with self.assertRaises(ValidationError) as e:
            self.yaml_upload_wizard._extract_yaml_data()
        self.assertEqual(
            e.exception.name,
            _("Yaml file doesn't contain valid data"),
            "Exception message does not match",
        )

        # -- 5 --
        # Test if TypeError is handled properly
        self.non_unicode_yaml_file = base64.b64encode(b"\x80")
        self.yaml_upload_wizard.yaml_file = self.non_unicode_yaml_file
        with self.assertRaises(ValidationError) as e:
            self.yaml_upload_wizard._extract_yaml_data()
        self.assertEqual(
            e.exception.name,
            _("YAML file cannot be decoded properly"),
            "Exception message does not match",
        )

        # -- 6 --
        # Test if YAML file is empty
        self.empty_yaml_file = ""
        self.yaml_upload_wizard.yaml_file = self.empty_yaml_file
        with self.assertRaises(ValidationError) as e:
            self.yaml_upload_wizard._extract_yaml_data()
        self.assertEqual(
            e.exception.name,
            _("File contains non-unicode characters or is empty"),
            "Exception message does not match",
        )

        # -- 7 --
        # Test if YAML file with unsupported YAML version is handled properly
        yaml_with_unsupported_version = self.yaml_code.replace(
            f"cetmix_tower_yaml_version: {self.FlightPlan.CETMIX_TOWER_YAML_VERSION}",
            f"cetmix_tower_yaml_version: {self.FlightPlan.CETMIX_TOWER_YAML_VERSION + 1}",  # noqa: E501
        )
        self.unsupported_yaml_version_yaml_file = base64.b64encode(
            yaml_with_unsupported_version.encode("utf-8")
        )
        self.yaml_upload_wizard.yaml_file = self.unsupported_yaml_version_yaml_file
        with self.assertRaises(ValidationError) as e:
            self.yaml_upload_wizard._extract_yaml_data()
        self.assertEqual(
            e.exception.name,
            _(
                "YAML file version is not supported."
                " You may need to update the Cetmix Tower Yaml module."
            ),
            "Exception message does not match",
        )

    def test_action_import_yaml_update_existing_record(self):
        """Test YAML import wizard action when updating an existing record"""

        # -- 1 --
        # Test if new import wizard record is created properly
        self.assertEqual(
            self.import_wizard_action["res_model"],
            "cx.tower.yaml.import.wiz",
            "Import wizard action model is not correct",
        )
        self.assertEqual(
            self.import_wizard_action["view_mode"],
            "form",
            "Import wizard action view mode is not correct",
        )

        self.assertEqual(
            self.import_wizard.model_name,
            "cx.tower.server.template",
            "Import wizard model name is not correct",
        )

        # -- 2 --
        # Modify Server Template name and variable value
        self.import_wizard.yaml_code = self.import_wizard.yaml_code.replace(
            "name: Test Server Template",
            "name: Updated Test Server Template",
        ).replace(
            "value_char: Some Test Value",
            "value_char: Updated Test Value",
        )
        variable_value_to_update = (
            self.server_template_yaml_test.variable_value_ids.filtered(
                lambda v: v.value_char == "Some Test Value"
            )
        )

        # Run import wizard action another time
        import_wizard_result_action = self.import_wizard.action_import_yaml()

        # -- 3 --
        # Test if record is updated properly
        self.assertEqual(
            import_wizard_result_action["res_model"],
            "cx.tower.server.template",
            "Import wizard action model is not correct",
        )
        self.assertEqual(
            import_wizard_result_action["res_id"],
            self.server_template_yaml_test.id,
            "ID must match existing record ID",
        )
        self.assertEqual(
            self.server_template_yaml_test.name,
            "Updated Test Server Template",
            "Record is not updated properly",
        )
        self.assertEqual(
            variable_value_to_update.value_char,
            "Updated Test Value",
            "Variable value is not updated properly",
        )

        # -- 4 --
        # Test if server log remains the same
        self.assertEqual(
            len(self.server_template_yaml_test.server_log_ids),
            1,
            "Server Log must remain the same",
        )
        self.assertEqual(
            self.server_log_yaml_test.id,
            self.server_template_yaml_test.server_log_ids.id,
            "Server Log must remain the same",
        )

    def test_action_import_yaml_create_new_record(self):
        """Test YAML import wizard action when creating a new record"""
        self.import_wizard.update_existing_record = False
        import_wizard_result_action = self.import_wizard.action_import_yaml()

        # -- 1 --
        # Test if new record is created instead of updating existing one
        self.assertEqual(
            import_wizard_result_action["res_model"],
            "cx.tower.server.template",
            "Import wizard action model is not correct",
        )
        self.assertNotEqual(
            import_wizard_result_action["res_id"],
            self.server_template_yaml_test.id,
            "ID must not match existing record ID",
        )

        # -- 2 --
        # Ensure that existing flight plan is used instead of creating a new one
        new_server_template = self.env[import_wizard_result_action["res_model"]].browse(
            import_wizard_result_action["res_id"]
        )
        self.assertEqual(
            new_server_template.flight_plan_id,
            self.flight_plan_yaml_test,
            "Existing flight plan must be used",
        )

        # -- 3 --
        # Ensure that existing tags are used instead of creating new ones
        for tag in self.server_template_yaml_test.tag_ids:
            self.assertIn(
                tag,
                new_server_template.tag_ids,
                "Existing tag must be used",
            )

        # -- 4 --
        # Ensure that new variable values are created
        for variable_value in self.server_template_yaml_test.variable_value_ids:
            self.assertNotIn(
                variable_value,
                new_server_template.variable_value_ids,
                "New variable value must be created instead of updating existing one",
            )

        # -- 5 --
        # Test if server log is created instead of updated
        for server_log in self.server_template_yaml_test.server_log_ids:
            self.assertNotIn(
                server_log,
                new_server_template.server_log_ids,
                "New Server Log must be created instead of updating existing one",
            )
