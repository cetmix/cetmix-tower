# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import base64

import yaml

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

    def test_yaml_export_wizard_yaml_generation(self):
        """Test code generation of YAML export wizard."""

        wizard_yaml = """
# This file is generated with Cetmix Tower.
# Details and documentation: https://cetmix.com/tower
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
  if_file_exists: skip
  disconnect_file: false
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
  if_file_exists: skip
  disconnect_file: false
"""

        # -- 1 --
        # Test with two commands
        context = {
            "default_explode_child_records": True,
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

    def test_reference_object_uniqueness(self):
        """
        Ensure each reference is exported as a full object only once
        (other times only as ref).
        """

        # Prepare YAML export for flight_plan with two same commands
        self.flight_plan_test_wizard.line_ids = [
            (0, 0, {"command_id": self.command_test_wizard.id}),
            (0, 0, {"command_id": self.command_test_wizard.id}),
        ]

        # Prepare YAML code
        self.test_wizard.onchange_explode_child_records()
        yaml_data = yaml.safe_load(self.test_wizard.yaml_code)

        # reference counters
        ref_full = set()
        ref_refs = set()

        # Recursively walk through the YAML data and count references
        def walk(obj):
            if isinstance(obj, dict):
                ref = obj.get("reference")
                # dict only with "reference" = ref, otherwise — full object
                if ref:
                    if list(obj.keys()) == ["reference"]:
                        ref_refs.add(ref)
                    else:
                        ref_full.add(ref)
                for v in obj.values():
                    walk(v)
            elif isinstance(obj, list):
                for v in obj:
                    walk(v)

        # Walk through the YAML data
        walk(yaml_data["records"])

        # Each reference as a full object — only once
        for ref in ref_full:
            self.assertEqual(
                list(ref_full).count(ref),
                1,
                f"Reference '{ref}' appears as a full object more than once",
            )
        # Check that no full objects appear more than once
        self.assertEqual(
            len(ref_full),
            len(set(ref_full)),
            "Some full objects appear more than once",
        )

        # Check that for each ref there is no only reference, but no full object
        for ref in ref_refs:
            self.assertIn(
                ref,
                ref_full,
                f"Reference '{ref}' is used only as a reference, "
                "but no full object present",
            )

    def test_export_required_model_name_in_yaml(self):
        """
        Test that the model name is required in the YAML file for each record
        """
        # create a command to run flight plan
        command_run_flight_plan = self.TowerCommand.create(
            {
                "name": "Run Flight Plan",
                "action": "plan",
                "flight_plan_id": self.flight_plan_test_wizard.id,
            }
        )
        # export 2 commands: command_run_flight_plan and command_test_wizard
        wizard = self.YamlExportWizard.with_context(
            active_model="cx.tower.command",
            active_ids=[command_run_flight_plan.id, self.command_test_wizard.id],
        ).create({})

        wizard.onchange_explode_child_records()

        yaml_data = yaml.safe_load(wizard.yaml_code)

        # check that the model name is present in the YAML file for each record
        for record in yaml_data["records"]:
            self.assertIn("cetmix_tower_model", record)

    def test_default_yaml_file_name_is_used(self):
        """
        Wizard should pre-fill `yaml_file_name` with the auto-generated
        value that ends with '.yaml' and contains the model prefix.
        """
        wiz = self.YamlExportWizard.with_context(
            active_model="cx.tower.command",
            active_ids=[self.command_test_wizard.id],
        ).create({})

        default_name = wiz.yaml_file_name

        self.assertFalse(
            default_name.endswith(".yaml"),
            "Default file name must NO have .yaml suffix",
        )
        self.assertIn(
            "command_",
            default_name,
            "Default file name should include model prefix",
        )

    def test_yaml_file_name_is_auto_fixed(self):
        """
        When the user assigns an invalid name, wizard should auto-sanitise
        it to a safe *basename* (lowercase, underscores, no extension).
        """
        wiz = self.YamlExportWizard.with_context(
            active_model="cx.tower.command",
            active_ids=[self.command_test_wizard.id],
        ).create({})

        # user enters a 'dirty' name with spaces, capitals, symbols
        wiz.write({"yaml_file_name": "My File!@# .YAML"})

        # write() override strips to a basename WITHOUT '.yaml'
        self.assertEqual(
            wiz.yaml_file_name,
            "my_file",
            "Wizard field must hold only the cleaned basename, without extension",
        )

    def test_action_generate_appends_extension(self):
        """
        When generating the download record, the system must append
        the `.yaml` extension to the sanitized basename.
        """
        wiz = self.YamlExportWizard.with_context(
            active_model="cx.tower.command",
            active_ids=[self.command_test_wizard.id],
        ).create({})
        wiz.onchange_explode_child_records()
        act = wiz.action_generate_yaml_file()
        download = self.env["cx.tower.yaml.export.wiz.download"].browse(act["res_id"])
        self.assertTrue(download.yaml_file_name.endswith(".yaml"))

    def test_custom_requires_text(self):
        """Creating a template with license 'custom' but no text must fail"""
        with self.assertRaises(ValidationError):
            self.env["cx.tower.yaml.manifest.tmpl"].create(
                {
                    "name": "Bad Manifest",
                    "license": "custom",
                }
            )

        tmpl_ok = self.env["cx.tower.yaml.manifest.tmpl"].create(
            {
                "name": "Good Manifest",
                "license": "custom",
                "license_text": "Custom license terms",
            }
        )
        self.assertEqual(tmpl_ok.license, "custom")
        self.assertEqual(tmpl_ok.license_text, "Custom license terms")

        with self.assertRaises(ValidationError):
            self.env["cx.tower.yaml.manifest.tmpl"].create(
                {
                    "name": "Bad Manifest 2",
                    "license": "custom",
                    "license_text": "    ",
                }
            )

    def test_wizard_resets_price_on_license_change(self):
        """Wizard must reset price/currency when license changes away from 'custom'"""
        wiz = self.YamlExportWizard.new(
            {
                "manifest_license": "custom",
                "manifest_price": 42.0,
                "manifest_currency": "EUR",
            }
        )
        wiz.manifest_license = "agpl-3"
        wiz._onchange_manifest_license()
        self.assertEqual(wiz.manifest_price, 0.0)
        self.assertFalse(wiz.manifest_currency)

        wiz.manifest_price = 7.5
        wiz.manifest_currency = "USD"
        wiz.manifest_license = "custom"
        wiz._onchange_manifest_license()
        self.assertEqual(wiz.manifest_price, 7.5)
        self.assertEqual(wiz.manifest_currency, "USD")
