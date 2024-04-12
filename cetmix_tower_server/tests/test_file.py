from unittest.mock import patch

from odoo import exceptions

from .common import TestTowerCommon


class TestTowerCommand(TestTowerCommon):
    def setUp(self):
        super().setUp()
        self.file_template = self.env["cx.tower.file.template"].create(
            {
                "name": "Test",
                "file_name": "test.txt",
                "server_dir": "/var/tmp",
                "code": "Hello, world!",
            }
        )
        self.file = self.env["cx.tower.file"].create(
            {
                "source": "tower",
                "template_id": self.file_template.id,
                "server_id": self.server_test_1.id,
            }
        )
        self.file_2 = self.env["cx.tower.file"].create(
            {
                "name": "test.txt",
                "source": "server",
                "server_id": self.server_test_1.id,
                "server_dir": "/var/tmp",
            }
        )

    def test_upload_file(self):
        """
        Upload file from tower to server
        """
        cx_tower_server_obj = self.registry["cx.tower.server"]

        def upload_file(this, file, remote_path):
            if file == "Hello, world!" and remote_path == "/var/tmp":
                return "ok"

        with patch.object(cx_tower_server_obj, "upload_file", upload_file):
            self.file.action_push_to_server()
            self.assertEqual(self.file.server_response, "ok")

    def test_delete_file(self):
        """
        Delete file remotely from server
        """
        cx_tower_server_obj = self.registry["cx.tower.server"]

        def delete_file(this, remote_path):
            if remote_path == "/var/tmp":
                return "ok"

        with patch.object(cx_tower_server_obj, "delete_file", delete_file):
            self.file.action_delete_from_server()
            self.assertEqual(self.file.server_response, "ok")

    def test_delete_file_access(self):
        """
        Test delete file access
        """
        with self.assertRaises(exceptions.AccessError):
            self.file.with_user(self.user_bob).delete(raise_error=True)

    def test_download_file(self):
        """
        Download file from server to tower
        """

        def download_file(this, remote_path):
            if remote_path == "/var/tmp/test.txt":
                return "Hello, world!"

        cx_tower_server_obj = self.registry["cx.tower.server"]

        with patch.object(cx_tower_server_obj, "download_file", download_file):
            self.file_2.action_pull_from_server()
            self.assertEqual(self.file_2.code, "Hello, world!")

    def test_get_current_server_code(self):
        """
        Download file from server to tower
        """
        cx_tower_server_obj = self.registry["cx.tower.server"]

        def upload_file(this, file, remote_path):
            if file == "Hello, world!" and remote_path == "/var/tmp":
                return "ok"

        with patch.object(cx_tower_server_obj, "upload_file", upload_file):
            self.file.action_push_to_server()
            self.assertEqual(self.file.server_response, "ok")

        def download_file(this, remote_path):
            if remote_path == "/var/tmp/test.txt":
                return "Hello, world!"

        with patch.object(cx_tower_server_obj, "download_file", download_file):
            self.file.action_get_current_server_code()
            self.assertEqual(self.file.code_on_server, "Hello, world!")

    def test_modify_template_code(self):
        code = "Pepe frog is happy as always"
        self.file_template.code = code

        # Check file code before modifications
        self.assertTrue(
            self.file.code == code,
            msg="File code should be the same as template before any modifications",
        )

        # Make possible to modify file code
        self.file.action_modify_code()

        # Check if template was removed from file
        self.assertFalse(
            self.file.template_id,
            msg="File template should be removed after modifying code.",
        )

        # Check if file code remains the same
        self.assertTrue(
            self.file.code == code, msg="File code should be the same as template."
        )
