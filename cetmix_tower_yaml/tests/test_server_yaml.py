# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""
Tests for cx.tower.server YAML export/import covering command_ids and plan_ids.
"""

import yaml

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestServerYAML(TransactionCase):
    """YAML export/import tests for cx.tower.server with commands and plans."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Server = env["cx.tower.server"]
        cls.Command = env["cx.tower.command"]
        cls.Plan = env["cx.tower.plan"]

        # Create a command to attach (use defaults for access_level)
        cls.command = cls.Command.create(
            {
                "name": "Test Command",
                "reference": "test_command",
                "action": "ssh_command",
                "allow_parallel_run": False,
            }
        )

        # Create a flight plan to attach
        cls.plan = cls.Plan.create(
            {
                "name": "Test Flight Plan",
                "reference": "test_plan",
                "allow_parallel_run": False,
                "color": 0,
            }
        )

        # Create server and link command and plan
        cls.server = cls.Server.create(
            {
                "name": "Server YAML Test",
                "reference": "srv_yaml_test",
                "ip_v4_address": "127.0.0.1",
                "ssh_username": "admin",
                "ssh_port": 22,
                "ssh_auth_mode": "p",
                "ssh_password": "dummy",
                "use_sudo": False,
                # Link the m2m fields
                "command_ids": [(6, 0, [cls.command.id])],
                "plan_ids": [(6, 0, [cls.plan.id])],
            }
        )

    def test_yaml_export_contains_command_and_plan(self):
        """Exported YAML include command_ids and plan_ids with correct references."""
        data = yaml.safe_load(self.server.yaml_code)
        # Check command_ids
        self.assertIn(
            "command_ids",
            data,
            "`command_ids` is missing from YAML export",
        )
        self.assertIsInstance(
            data["command_ids"], list, "`command_ids` should be a list in YAML"
        )
        self.assertTrue(
            data["command_ids"],
            "`command_ids` list should not be empty",
        )
        # Only reference should be exported
        self.assertEqual(
            data["command_ids"][0],
            self.command.reference,
            "Exported command reference does not match",
        )

        # Check plan_ids
        self.assertIn(
            "plan_ids",
            data,
            "`plan_ids` is missing from YAML export",
        )
        self.assertIsInstance(
            data["plan_ids"], list, "`plan_ids` should be a list in YAML"
        )
        self.assertTrue(
            data["plan_ids"],
            "`plan_ids` list should not be empty",
        )
        self.assertEqual(
            data["plan_ids"][0],
            self.plan.reference,
            "Exported plan reference does not match",
        )

    def test_yaml_roundtrip_restores_command_and_plan(self):
        """A full export→delete→import cycle must restore the m2m relations."""
        yaml_dict = yaml.safe_load(self.server.yaml_code)
        # Remove original server
        self.server.unlink()
        # Prepare values and import
        vals = self.Server._post_process_yaml_dict_values(yaml_dict)
        restored = self.Server.with_context(
            from_yaml=True, skip_ssh_settings_check=True
        ).create(vals)

        # Verify m2m links restored
        self.assertEqual(
            restored.command_ids.ids,
            [self.command.id],
            "`command_ids` were not restored correctly",
        )
        self.assertEqual(
            restored.plan_ids.ids,
            [self.plan.id],
            "`plan_ids` were not restored correctly",
        )
