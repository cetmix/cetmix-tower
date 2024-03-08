from unittest.mock import patch

from odoo.addons.cetmix_tower_server.tests.test_common import TestTowerCommon


class TestTowerCommand(TestTowerCommon):
    def test_upload_file(self):
        """
        Upload file from tower to server
        """
        file_template = self.env["cx.tower.file.template"].create(
            {
                "name": "Test",
                "file_name": "test.txt",
                "server_dir": "/var/tmp",
                "code": "Hello, world!",
            }
        )
        file = self.env["cx.tower.file"].create(
            {
                "source": "tower",
                "template_id": file_template.id,
                "server_id": self.server_test_1.id,
            }
        )

        cx_tower_server_obj = self.registry["cx.tower.server"]

        def upload_file(this, file, remote_path):
            if file == "Hello, world!" and remote_path == "/var/tmp":
                return "ok"

        with patch.object(cx_tower_server_obj, "upload_file", upload_file):
            file.action_push_to_server()
            self.assertEqual(file.sync_code, "ok")

    def test_download_file(self):
        """
        Download file from server to tower
        """
        file = self.env["cx.tower.file"].create(
            {
                "name": "test.txt",
                "source": "server",
                "server_id": self.server_test_1.id,
                "server_dir": "/var/tmp",
            }
        )

        def download_file(this, remote_path):
            if remote_path == "/var/tmp/test.txt":
                return "Hello, world!"

        cx_tower_server_obj = self.registry["cx.tower.server"]

        with patch.object(cx_tower_server_obj, "download_file", download_file):
            file.action_pull_from_server()
            self.assertEqual(file.code, "Hello, world!")

    def test_get_current_server_code(self):
        """
        Download file from server to tower
        """
        file_template = self.env["cx.tower.file.template"].create(
            {
                "name": "Test",
                "file_name": "test.txt",
                "server_dir": "/var/tmp",
                "code": "Hello, world!",
            }
        )
        file = self.env["cx.tower.file"].create(
            {
                "source": "tower",
                "template_id": file_template.id,
                "server_id": self.server_test_1.id,
            }
        )

        cx_tower_server_obj = self.registry["cx.tower.server"]

        def upload_file(this, file, remote_path):
            if file == "Hello, world!" and remote_path == "/var/tmp":
                return "ok"

        with patch.object(cx_tower_server_obj, "upload_file", upload_file):
            file.action_push_to_server()
            self.assertEqual(file.sync_code, "ok")

        def download_file(this, remote_path):
            if remote_path == "/var/tmp/test.txt":
                return "Hello, world!"

        with patch.object(cx_tower_server_obj, "download_file", download_file):
            file.action_get_current_server_code()
            self.assertEqual(file.code_on_server, "Hello, world!")

    def test_modify_template_code(self):
        code = "Pepe frog is happy as always"
        file_template = self.env["cx.tower.file.template"].create(
            {
                "name": "Test",
                "file_name": "test.txt",
                "server_dir": "/var/tmp",
                "code": code,
            }
        )
        file = self.env["cx.tower.file"].create(
            {
                "source": "tower",
                "template_id": file_template.id,
                "server_id": self.server_test_1.id,
            }
        )

        # Check file code before modifications
        self.assertTrue(
            file.code == code,
            msg="File code should be the same as template before any modifications",
        )

        # Make possible to modify file code
        file.action_modify_code()

        # Check if template was removed from file
        self.assertFalse(
            file.template_id,
            msg="File template should be removed after modifying code.",
        )

        # Check if file code remains the same
        self.assertTrue(
            file.code == code, msg="File code should be the same as template."
        )
