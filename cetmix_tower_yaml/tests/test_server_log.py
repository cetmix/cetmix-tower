# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""
Tests for the cx.tower.server.log model YAML export/import.

Covers:
1. YAML export of a file-type log must include `file_id` and allow suffixes.
2. A full round-trip (export → delete → import) preserves the `file_id` relation.
3. Exporting a non-file log must include a falsy `file_id`.
4. Importing YAML with a bogus `file_id` reference raises ValidationError.
"""

import yaml

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestServerLog(TransactionCase):
    """YAML export/import tests for cx.tower.server.log."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.File = env["cx.tower.file"]
        cls.Server = env["cx.tower.server"]
        cls.ServerLog = env["cx.tower.server.log"]

        # Create a file to reference from the log
        cls.file = cls.File.create(
            {
                "name": "repos.yaml",
                "reference": "reposyaml",
                "source": "tower",
                "file_type": "text",
                "server_dir": "/tmp",
                "code": "# Example\nHello, Tower!",
            }
        )

        # Create a server (use password auth to satisfy constraints)
        cls.server = cls.Server.create(
            {
                "name": "Srv-YAML-Test",
                "reference": "srv_yaml_test",
                "ip_v4_address": "127.0.0.1",
                "ssh_username": "admin",
                "ssh_port": 22,
                "ssh_auth_mode": "p",
                "ssh_password": "dummy",
                "use_sudo": False,
            }
        )

        # Create a file-type log linked to the file above
        cls.log = cls.ServerLog.create(
            {
                "name": "Log from file",
                "reference": "log_from_file",
                "log_type": "file",
                "file_id": cls.file.id,
                "server_id": cls.server.id,
                "use_sudo": False,
            }
        )

    def test_yaml_export_contains_file_id(self):
        """Exported YAML must include a file_id starting with the file's reference."""
        data = yaml.safe_load(self.log.yaml_code)
        # Ensure file_id is present
        self.assertIn("file_id", data, "`file_id` is missing from YAML export")
        # Allow for auto-appended suffixes, so only check prefix
        self.assertTrue(
            data["file_id"].startswith(self.file.reference),
            f"`file_id` value '{data['file_id']}' should start with "
            f"'{self.file.reference}'",
        )

    def test_yaml_roundtrip_restores_file_id(self):
        """A full export→delete→import cycle must restore the file_id relation."""
        yaml_dict = yaml.safe_load(self.log.yaml_code)
        # Remove the original log
        self.log.unlink()
        # Recreate from YAML
        vals = self.ServerLog._post_process_yaml_dict_values(yaml_dict)
        restored = self.ServerLog.with_context(from_yaml=True).create(vals)
        # Verify relation restored
        self.assertEqual(
            restored.file_id.id,
            self.file.id,
            "`file_id` was not restored after round-trip",
        )

    def test_yaml_export_without_file_id(self):
        """Logs of non-file type should not include file_id in YAML."""
        cmd_log = self.ServerLog.create(
            {
                "name": "Log no file",
                "reference": "log_no_file",
                "log_type": "command",
                "server_id": self.server.id,
                "use_sudo": False,
            }
        )
        data = yaml.safe_load(cmd_log.yaml_code)
        # key is present, but must be falsy
        self.assertIn("file_id", data, "`file_id` key is missing")
        self.assertFalse(
            data["file_id"],
            "`file_id` for non-file log must be False/empty",
        )

    def test_yaml_import_with_missing_file_reference(self):
        """Missing file reference is accepted, but file_id stays empty."""
        yaml_dict = yaml.safe_load(self.log.yaml_code)
        yaml_dict["file_id"] = "does_not_exist"

        vals = self.ServerLog._post_process_yaml_dict_values(yaml_dict)
        new_log = self.ServerLog.with_context(from_yaml=True).create(vals)

        # Log is created, but the relation is not resolved
        self.assertFalse(
            new_log.file_id,
            "file_id should be empty when reference cannot be resolved",
        )
