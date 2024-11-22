import base64

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase


class TestYamlExportWizard(TransactionCase):
    def setUp(self, *args, **kwargs):
        super().setUp(*args, **kwargs)

        # Create a command
        self.TowerCommand = self.env["cx.tower.command"]
        self.command_test_wizard = self.TowerCommand.create(
            {
                "reference": "test_command_from_yaml",
                "name": "Test Command From Yaml",
                "code": "echo 'Test Command From Yaml'",
            }
        )

        # Create a wizard and trigger onchange
        self.YamlExportWizard = self.env["cx.tower.yaml.export.wiz"]
        self.test_wizard = self.YamlExportWizard.with_context(
            active_model="cx.tower.command",
            active_ids=[self.command_test_wizard.id],
        ).create({})
        self.test_wizard.onchange_explode_child_records()

    def test_user_without_export_group_cannot_export(self):
        """Test if user without export group cannot export"""

        # Tower manager user without export group
        self.user_yaml_export = (
            self.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "No Yaml Export User",
                    "login": "no_yaml_export_user",
                    "groups_id": [
                        (4, self.env.ref("cetmix_tower_server.group_manager").id)
                    ],
                }
            )
        )
        with self.assertRaises(AccessError):
            self.test_wizard.with_user(self.user_yaml_export).read([])

    def test_comment_inserted_into_yaml_code(self):
        """Test if comment is inserted into YAML code"""
        self.test_wizard.comment = "Test Comment"
        self.test_wizard.onchange_explode_child_records()
        first_line_of_yaml_code = self.test_wizard.yaml_code.split("\n")[0]
        self.assertEqual(
            first_line_of_yaml_code,
            f"# {self.test_wizard.comment}",
            "Comment should be properly prepended to YAML code",
        )

    def test_yaml_export_wizard(self):
        """Test the YAML export wizard."""

        # -- 1 --
        # Test wizard creation
        self.assertEqual(
            self.test_wizard.yaml_code,
            self.command_test_wizard.yaml_code,
            "YAML code should be the same",
        )

        # -- 2 --
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

        # -- 3 --
        # Ensure download wizard file name is generated
        # based on the record reference
        download_wizard = self.env["cx.tower.yaml.export.wiz.download"].browse(
            result["res_id"]
        )
        self.assertEqual(
            download_wizard.yaml_file_name,
            f"command_{self.command_test_wizard.reference}.yaml",
            "YAML file name should be generated based on record reference",
        )

        # -- 4 --
        # Decode YAML file and check if it's valid
        yaml_file_content = base64.decodebytes(download_wizard.yaml_file).decode(
            "utf-8"
        )
        self.assertEqual(
            yaml_file_content,
            self.command_test_wizard.yaml_code,
            "YAML file content should be the same as the original YAML code",
        )

        # -- 5 --
        # Test if empty YAML code is handled correctly
        self.test_wizard.yaml_code = ""
        with self.assertRaises(ValidationError):
            self.test_wizard.action_generate_yaml_file()

        # -- 6 --
        # Test non utf-8 characters encoding
        self.test_wizard.yaml_code = "Non-ascii characters: \udc80"
        with self.assertRaises(ValidationError):
            self.test_wizard.action_generate_yaml_file()
