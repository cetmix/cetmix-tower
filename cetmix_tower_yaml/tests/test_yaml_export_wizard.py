# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import base64

from odoo.exceptions import AccessError, ValidationError

from odoo.addons.base.tests.common import BaseCommon


class TestYamlExportWizard(BaseCommon):
    @classmethod
    def setUpClass(cls, *args, **kwargs):
        super().setUpClass(*args, **kwargs)

        # Used to ensure that the file header
        # is present in the YAML code
        cls.file_header = """
# This file is generated with Cetmix Tower.
# Details and documentation: https://cetmix.com/tower
"""
        # Create a command
        cls.TowerCommand = cls.env["cx.tower.command"]
        cls.command_test_wizard = cls.TowerCommand.create(
            {
                "reference": "test_command_from_yaml",
                "name": "Test Command From Yaml",
                "code": "echo 'Test Command From Yaml'",
            }
        )
        cls.command_test_wizard_2 = cls.TowerCommand.create(
            {
                "reference": "test_command_from_yaml_2",
                "name": "Test Command From Yaml 2",
                "code": "echo 'Test Command From Yaml 2'",
            }
        )

        # Create a flight plan
        cls.FlightPlan = cls.env["cx.tower.plan"]
        cls.flight_plan_test_wizard = cls.FlightPlan.create(
            {
                "name": "Test Flight Plan From Yaml",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "command_id": cls.command_test_wizard.id,
                        },
                    )
                ],
            }
        )

        # Create a server template
        cls.ServerTemplate = cls.env["cx.tower.server.template"]
        cls.server_template_test_wizard = cls.ServerTemplate.create(
            {
                "name": "Test Server Template From Yaml",
                "flight_plan_id": cls.flight_plan_test_wizard.id,
            }
        )

        # Create a wizard and trigger onchange
        cls.YamlExportWizard = cls.env["cx.tower.yaml.export.wiz"]
        cls.test_wizard = cls.YamlExportWizard.with_context(
            active_model="cx.tower.server.template",
            active_ids=[cls.server_template_test_wizard.id],
        ).create({})
        cls.test_wizard.onchange_explode_child_records()

    def test_user_without_export_group_cannot_export(self):
        """Test if user without export group cannot export"""

        # Tower manager user without export group
        self.user_yaml_export = self.env["res.users"].create(
            {
                "name": "No Yaml Export User",
                "login": "no_yaml_export_user",
                "groups_id": [
                    (4, self.env.ref("cetmix_tower_server.group_manager").id)
                ],
            }
        )
        with self.assertRaises(AccessError):
            self.test_wizard.with_user(self.user_yaml_export).read([])

    def test_comment_inserted_into_yaml_code(self):
        """Test if comment is inserted into YAML code"""

        self.test_wizard.comment = "Test Comment"
        self.test_wizard.onchange_explode_child_records()
        # Because header takes 3 lines, we need to check the 4th line
        fourth_line_of_yaml_code = self.test_wizard.yaml_code.split("\n")[3]
        self.assertEqual(
            fourth_line_of_yaml_code,
            f"# {self.test_wizard.comment}",
            "Comment should be properly prepended to YAML code",
        )

    def test_yaml_export_wizard_yaml_generation(self):
        """Test code generation of YAML export wizard."""

        wizard_yaml = """
# This file is generated with Cetmix Tower.
# Details and documentation: https://cetmix.com/tower
# Test Comment
cetmix_tower_yaml_version: 1
records:
- cetmix_tower_model: command
  access_level: manager
  reference: test_command_from_yaml
  name: Test Command From Yaml
  action: ssh_command
  allow_parallel_run: false
  note: false
  path: false
  code: echo 'Test Command From Yaml'
  server_status: false
  no_split_for_sudo: false
- cetmix_tower_model: command
  access_level: manager
  reference: test_command_from_yaml_2
  name: Test Command From Yaml 2
  action: ssh_command
  allow_parallel_run: false
  note: false
  path: false
  code: echo 'Test Command From Yaml 2'
  server_status: false
  no_split_for_sudo: false
"""

        # -- 1 --
        # Test with two commands
        context = {
            "default_explode_child_records": True,
            "default_comment": "Test Comment",
            "default_remove_empty_values": True,
            "active_model": "cx.tower.command",
            "active_ids": [self.command_test_wizard.id, self.command_test_wizard_2.id],
        }
        wizard = self.YamlExportWizard.with_context(context).create({})  # pylint: disable=context-overridden # new need a new clean context
        wizard.onchange_explode_child_records()
        self.assertEqual(wizard.yaml_code, wizard_yaml)

    def test_yaml_export_wizard(self):
        """Test the YAML export wizard."""

        # -- 1 --
        # Test wizard action
        result = self.test_wizard.action_generate_yaml_file()
        self.assertEqual(
            result["type"], "ir.actions.act_window", "Action should be a window"
        )
        self.assertEqual(
            result["res_model"],
            "cx.tower.yaml.export.wiz.download",
            "Result model should be the download wizard",
        )
        self.assertTrue(result["res_id"], "Wizard should have been created")

        # -- 2 --
        # Ensure download wizard file name is generated
        # based on the record reference
        download_wizard = self.env["cx.tower.yaml.export.wiz.download"].browse(
            result["res_id"]
        )
        self.assertEqual(
            download_wizard.yaml_file_name,
            f"server_template_{self.server_template_test_wizard.reference}.yaml",
            "YAML file name should be generated based on record reference",
        )

        # -- 3 --
        # Decode YAML file and check if it's valid
        yaml_file_content = base64.decodebytes(download_wizard.yaml_file).decode(
            "utf-8"
        )
        self.assertEqual(
            yaml_file_content,
            self.test_wizard.yaml_code,
            "YAML file content should be the same as the original YAML code",
        )

        # -- 4 --
        # Test if empty YAML code is handled correctly
        self.test_wizard.yaml_code = ""
        with self.assertRaises(ValidationError):
            self.test_wizard.action_generate_yaml_file()
