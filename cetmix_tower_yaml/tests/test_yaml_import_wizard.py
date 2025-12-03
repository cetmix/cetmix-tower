# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


import base64

import yaml

from odoo import _
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase
from odoo.tools import mute_logger


class TestTowerYamlImportWizUpload(TransactionCase):
    """Test Tower YAML Import Wizard Upload"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Variables
        cls.Variable = cls.env["cx.tower.variable"]
        cls.variable_yaml_test = cls.Variable.create(
            {"name": "YAML Test", "reference": "yaml_test"}
        )
        cls.variable_yaml_url = cls.Variable.create(
            {"name": "YAML URL", "reference": "yaml_url"}
        )

        # Tags
        cls.Tag = cls.env["cx.tower.tag"]
        cls.tag_yaml_test = cls.Tag.create(
            {"name": "YAML Test", "reference": "yaml_test"}
        )
        cls.tag_another_yaml_test = cls.Tag.create(
            {"name": "Another YAML Test", "reference": "another_yaml_test"}
        )

        # Commands
        cls.Command = cls.env["cx.tower.command"]
        cls.command_yaml_test = cls.Command.create(
            {"name": "Test Yaml Command", "reference": "test_yaml_command"}
        )

        # Flight Plan
        cls.FlightPlan = cls.env["cx.tower.plan"]
        cls.flight_plan_yaml_test = cls.FlightPlan.create(
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
                            "command_id": cls.command_yaml_test.id,
                        },
                    ),
                ],
            }
        )

        # Create Server Template used for testing
        cls.server_template_yaml_test = cls.env["cx.tower.server.template"].create(
            {
                "name": "Test Server Template",
                "tag_ids": [
                    (4, cls.tag_yaml_test.id),
                    (4, cls.tag_another_yaml_test.id),
                ],
                "variable_value_ids": [
                    (
                        0,
                        0,
                        {
                            "variable_id": cls.variable_yaml_test.id,
                            "value_char": "Some Test Value",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "variable_id": cls.variable_yaml_url.id,
                            "value_char": "https://cetmix.com",
                        },
                    ),
                ],
                "flight_plan_id": cls.flight_plan_yaml_test.id,
            }
        )

        # Server Logs
        cls.ServerLog = cls.env["cx.tower.server.log"]
        cls.server_log_yaml_test = cls.ServerLog.create(
            {
                "name": "Test Server Log",
                "reference": "test_server_log",
                "command_id": cls.command_yaml_test.id,
                "log_type": "command",
                "server_template_id": cls.server_template_yaml_test.id,
            }
        )

        # Create an export wizard and generate YAML code
        context = {
            "active_model": "cx.tower.server.template",
            "active_ids": [cls.server_template_yaml_test.id],
        }
        cls.export_wizard = (
            cls.env["cx.tower.yaml.export.wiz"].with_context(context).create({})  # pylint: disable=context-overridden # new need a new clean context
        )
        cls.export_wizard.onchange_explode_child_records()
        cls.export_wizard.action_generate_yaml_file()
        cls.yaml_code = cls.export_wizard.yaml_code
        cls.yaml_file = base64.b64encode(cls.yaml_code.encode("utf-8"))

        # YAML import upload wizard
        cls.YamlImportWizUpload = cls.env["cx.tower.yaml.import.wiz.upload"]
        cls.yaml_upload_wizard = cls.YamlImportWizUpload.create(
            {"yaml_file": cls.yaml_file, "file_name": "test_yaml_file.yaml"}
        )

        # YAML import wizard
        cls.import_wizard_action = cls.yaml_upload_wizard.action_import_yaml()
        cls.import_wizard = cls.env[cls.import_wizard_action["res_model"]].browse(
            cls.import_wizard_action["res_id"]
        )
        cls.import_wizard.if_record_exists = "update"

    def test_extract_yaml_data(self):
        """Test extract YAML data from file"""

        # -- 1 --
        # Test if YAML file is valid
        extracted_yaml_data = self.yaml_upload_wizard._extract_yaml_data()
        self.assertEqual(
            extracted_yaml_data,
            self.yaml_code,
            "YAML code is not extracted correctly",
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
            str(e.exception),
            _("'invalid_model' is not a valid model"),
            "Exception message does not match",
        )
        # -- 3 --
        # Test if non YAML supported model is handled properly
        # Replace model name with non YAML supported model
        self.non_yaml_supported_yaml_code = self.yaml_code.replace(
            "server_template", "command_run_wizard"
        )
        self.non_yaml_supported_yaml_file = base64.b64encode(
            self.non_yaml_supported_yaml_code.encode("utf-8")
        )
        self.yaml_upload_wizard.yaml_file = self.non_yaml_supported_yaml_file
        with self.assertRaises(ValidationError) as e:
            self.yaml_upload_wizard._extract_yaml_data()
        self.assertEqual(
            str(e.exception),
            _("Model 'command_run_wizard' does not support YAML import"),
            "Exception message does not match",
        )

        # -- 4 --
        # Test if YAML that is not a dictionary is handled properly
        self.invalid_yaml_file = base64.b64encode(b"Invalid YAML file")
        self.yaml_upload_wizard.yaml_file = self.invalid_yaml_file
        with self.assertRaises(ValidationError) as e:
            self.yaml_upload_wizard._extract_yaml_data()
        self.assertEqual(
            str(e.exception),
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
            str(e.exception),
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
            str(e.exception),
            _("File is empty"),
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
            str(e.exception),
            _(
                "YAML version is higher than version"
                " supported by your Cetmix Tower instance."
                " %(code_version)s > %(tower_version)s",
                code_version=self.FlightPlan.CETMIX_TOWER_YAML_VERSION + 1,
                tower_version=self.FlightPlan.CETMIX_TOWER_YAML_VERSION,
            ),
            "Exception message does not match",
        )

        # -- 8 --
        # Test YAML file with no records
        self.import_wizard.yaml_code = "cetmix_tower_yaml_version: 1"
        with self.assertRaises(ValidationError) as e:
            self.import_wizard.action_import_yaml()
        self.assertEqual(
            str(e.exception),
            _("YAML file doesn't contain any records"),
            "Exception message does not match",
        )

    def test_action_import_yaml_skip_if_exists(self):
        """Test YAML import wizard action when skipping an existing record"""

        self.import_wizard.if_record_exists = "skip"

        # Run import wizard action
        import_wizard_result_action = self.import_wizard.action_import_yaml()

        # Test if action is composed properly
        self.assertEqual(
            import_wizard_result_action["type"],
            "ir.actions.client",
            "Import wizard action type is not correct",
        )
        self.assertEqual(
            import_wizard_result_action["tag"],
            "display_notification",
            "Import wizard action tag is not correct",
        )
        self.assertEqual(
            import_wizard_result_action["params"]["title"],
            _("Record Import"),
            "Import wizard action title is not correct",
        )
        self.assertEqual(
            import_wizard_result_action["params"]["message"],
            _("No records were created or updated"),
            "Import wizard action message is not correct",
        )
        self.assertEqual(
            import_wizard_result_action["params"]["sticky"],
            True,
            "Import wizard action sticky is not correct",
        )
        self.assertEqual(
            import_wizard_result_action["params"]["type"],
            "warning",
            "Import wizard action type is not correct",
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
            import_wizard_result_action["domain"],
            [("id", "in", self.server_template_yaml_test.ids)],
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
        self.import_wizard.if_record_exists = "create"
        with mute_logger("odoo.addons.cetmix_tower_yaml.models.cx_tower_yaml_mixin"):
            import_wizard_result_action = self.import_wizard.action_import_yaml()

        # -- 1 --
        # Test if new record is created instead of updating existing one
        self.assertEqual(
            import_wizard_result_action["res_model"],
            "cx.tower.server.template",
            "Import wizard action model is not correct",
        )
        self.assertNotEqual(
            import_wizard_result_action["domain"],
            f"[('id', '=', {self.server_template_yaml_test.ids})]",
            "ID must not match existing record ID",
        )

        # -- 2 --
        # Ensure that existing flight plan is used instead of creating a new one
        new_server_template = self.env[import_wizard_result_action["res_model"]].search(
            import_wizard_result_action["domain"]
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

    def test_extract_secret_names(self):
        """Test extract secret names from YAML data"""

        # NB: this is not a real model, it's just for testing
        yaml_code = """cetmix_tower_yaml_version: 1
records:
- cetmix_tower_model: test_model
  access_level: manager
  reference: such_much_test_record
  name: Such Much Command
  action: file_using_template
  allow_parallel_run: false
  note: Just a note
  os_ids: false
  tag_ids: false
  path: false
  file_template_id: false
  flight_plan_id: false
  code: false
  variable_ids: false
  secret_ids: false
  ssh_key_id:
    reference: test_ssh_key
    name: Test SSH Key
    key_type: k
    note: false
- cetmix_tower_model: another_test_model
  reference: such_much_test_record_2
  name: Such Much Test Record 2
  note: Just a note 2
  ssh_key_id:
    reference: test_ssh_key
    name: Test SSH Key
    key_type: k
    note: false
    secret_ids:
    - reference: secret_2
      name: Secret 2
      key_type: s
      note: false
    - reference: secret_3
      name: Secret 3
      key_type: s
      note: false
- cetmix_tower_model: another_test_model
  reference: such_much_test_record_3
  name: Such Much Test Record 3
  note: Just a note 3
  ssh_key_id:
    reference: another_ssh_key
    name: Another SSH Key
  sub_record:
    reference: such_much_test_record_4
    name: Such Much Test Record 4
    note: Just a note 4
    secret_ids:
    - reference: secret_1
      name: Secret 3
      key_type: s
      note: false
    - reference: secret_2
      name: Secret 4
      key_type: s
      note: false
  file_template_id:
    reference: my_custom_test_template
    name: Such much demo
    source: tower
    file_type: text
    server_dir: /var/log/my/files
    file_name: much_logs.txt
    keep_when_deleted: false
    tag_ids: false
    note: Hey!
    code: false
    variable_ids: false
    secret_ids: false
  flight_plan_id: false
  code: false
  variable_ids: false
  secret_ids:
  - reference: secret_1
    name: Secret 1
    key_type: s
    note: false
  - reference: secret_2
    name: Secret 2
    key_type: s
    note: false
"""
        secret_list = self.env["cx.tower.yaml.import.wiz"]._extract_secret_names(
            yaml.safe_load(yaml_code)
        )
        # We expect 6 secrets in the list:
        # 2 keys: 'Test SSH Key', 'Another SSH Key'
        # 4 secrets: 'Secret 3', 'Secret 4', 'Secret 1', 'Secret 2'
        self.assertEqual(len(secret_list), 6, "Secret list length is not correct")
        self.assertIn("Test SSH Key", secret_list, "Key is not in the list")
        self.assertIn("Another SSH Key", secret_list, "Key is not in the list")
        self.assertIn("Secret 3", secret_list, "Key is not in the list")
        self.assertIn("Secret 4", secret_list, "Key is not in the list")
        self.assertIn("Secret 1", secret_list, "Key is not in the list")
        self.assertIn("Secret 2", secret_list, "Key is not in the list")

    def test_extract_secret_names_with_key_id(self):
        """Test extract secret names when secrets are nested under key_id"""
        yaml_code = """cetmix_tower_yaml_version: 1
records:
- cetmix_tower_model: test_model
  reference: rec_1
  name: Test Record
  secret_ids:
    - key_id:
        reference: secret_1
        name: Nested Secret 1
    - key_id:
        reference: secret_2
        name: Nested Secret 2
  ssh_key_id:
    name: SSH Key Nested
"""
        secret_list = self.env["cx.tower.yaml.import.wiz"]._extract_secret_names(
            yaml.safe_load(yaml_code)
        )

        # We expect 3 secrets total:
        # - SSH Key Nested (from ssh_key_id)
        # - Nested Secret 1
        # - Nested Secret 2
        self.assertCountEqual(
            secret_list,
            ["Nested Secret 1", "Nested Secret 2", "SSH Key Nested"],
            "Unexpected secrets extracted for nested structure",
        )

    def test_create_records_different_models(self):
        """Test create records with different models"""

        yaml_code = """cetmix_tower_yaml_version: 1
records:
- cetmix_tower_model: command
  access_level: manager
  reference: much_much_command
  name: Much Much Command
  action: file_using_template
  allow_parallel_run: false
  note: Just a note
  os_ids: false
  tag_ids: false
  path: false
  file_template_id: false
  flight_plan_id: false
  code: false
  variable_ids: false
  secret_ids: false
  ssh_key_id:
    reference: test_ssh_key
    name: Test SSH Key
    key_type: k
    note: false
- cetmix_tower_model: server_template
  reference: wow_much_server_template
  name: Wow Much Server Template
  note: Just a note 2
- cetmix_tower_model: tag
  reference: such_much_tag
  name: Such Much Tag
"""
        # Create a new command record
        self.import_wizard.if_record_exists = "update"
        self.import_wizard.yaml_code = yaml_code

        action = self.import_wizard.action_import_yaml()

        # Check if action is composed properly
        self.assertEqual(
            action["type"],
            "ir.actions.client",
            "Import wizard action type is not correct",
        )
        self.assertEqual(
            action["tag"],
            "display_notification",
            "Import wizard action tag is not correct",
        )
        self.assertEqual(
            action["params"]["title"],
            _("Record Import"),
            "Import wizard action title is not correct",
        )
        self.assertEqual(
            action["params"]["type"],
            "success",
            "Import wizard action type is not correct",
        )
        self.assertEqual(
            action["params"]["sticky"],
            True,
            "Import wizard action sticky is not correct",
        )

        # Check command
        self.assertTrue(
            self.Command.get_by_reference("much_much_command"),
            "Command must be created",
        )

        # Check server template
        self.assertTrue(
            self.env["cx.tower.server.template"].get_by_reference(
                "wow_much_server_template"
            ),
            "Server template must be created",
        )

        # Check tag
        self.assertTrue(
            self.Tag.get_by_reference("such_much_tag"), "Tag must be created"
        )

    def test_yaml_import_server_without_password(self):
        """Wizard should import server without ssh_password."""
        yaml_code = (
            "cetmix_tower_yaml_version: 1\n"
            "records:\n"
            "- reference: srv_nopass\n"
            "  cetmix_tower_model: server\n"
            "  name: YAML NoPass\n"
            "  ssh_auth_mode: p\n"
            "  ssh_username: root\n"
            "  ip_v4_address: 10.0.0.3\n"
        )
        wiz = self.env["cx.tower.yaml.import.wiz"].create(
            {
                "yaml_code": yaml_code,
                "if_record_exists": "create",
            }
        )
        wiz.action_import_yaml()

        srv = self.env["cx.tower.server"].get_by_reference("srv_nopass")
        self.assertTrue(srv, "Server was not created")
        self.assertFalse(
            srv._get_secret_value("ssh_password"),
            "ssh_password must stay empty after import",
        )

    def test_orm_create_server_requires_password(self):
        """Creating a server via ORM/UI must fail when ssh_password is missing."""
        with self.assertRaises(ValidationError) as err:
            self.env["cx.tower.server"].create(
                {
                    "reference": "srv_ui",
                    "name": "UI NoPass",
                    "ssh_auth_mode": "p",
                    "ssh_username": "root",
                    "ip_v4_address": "10.0.0.2",
                }
            )
        self.assertIn("Please provide SSH password", str(err.exception))

    def test_yaml_import_server_with_skip_ssh_check(self):
        """Explicit skip_ssh_settings_check also bypasses password validation."""
        yaml_code = (
            "cetmix_tower_yaml_version: 1\n"
            "records:\n"
            "- reference: srv_skip\n"
            "  cetmix_tower_model: server\n"
            "  name: YAML Skip Check\n"
            "  ssh_auth_mode: p\n"
            "  ssh_username: root\n"
            "  ip_v4_address: 10.0.0.4\n"
        )
        wiz = self.env["cx.tower.yaml.import.wiz"].create(
            {
                "yaml_code": yaml_code,
                "if_record_exists": "create",
            }
        )
        wiz.with_context(skip_ssh_settings_check=True).action_import_yaml()

        srv = self.env["cx.tower.server"].get_by_reference("srv_skip")
        self.assertTrue(
            srv, "Server must be created when skip_ssh_settings_check is set"
        )
