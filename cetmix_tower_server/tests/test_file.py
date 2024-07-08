from unittest.mock import patch

from odoo import exceptions

from .common import TestTowerCommon


class TestTowerFile(TestTowerCommon):
    def setUp(self):
        super().setUp()
        self.file_template = self.FileTemplate.create(
            {
                "name": "Test",
                "file_name": "test.txt",
                "server_dir": "/var/tmp",
                "code": "Hello, world!",
            }
        )
        self.file = self.File.create(
            {
                "source": "tower",
                "template_id": self.file_template.id,
                "server_id": self.server_test_1.id,
            }
        )
        self.file_2 = self.File.create(
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
                return b"Hello, world!"
            elif remote_path == "/var/tmp/binary.zip":
                return b"Hello, world!\x00"

        cx_tower_server_obj = self.registry["cx.tower.server"]

        with patch.object(cx_tower_server_obj, "download_file", download_file):
            self.file_2.action_pull_from_server()
            self.assertEqual(self.file_2.code, "Hello, world!")

            self.file_2.name = "binary.zip"
            res = self.file_2.action_pull_from_server()
            self.assertTrue(
                isinstance(res, dict) and res["tag"] == "display_notification",
                msg=(
                    "If file type is 'text', then the result must be a dict "
                    "representing the display_notification action."
                ),
            )

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
                return b"Hello, world!"

        with patch.object(cx_tower_server_obj, "download_file", download_file):
            self.file.action_get_current_server_code()
            self.assertEqual(self.file.code_on_server, "Hello, world!")

    def test_modify_template_code(self):
        """Test how template code modification affects related files"""
        code = "Pepe frog is happy as always"
        self.file_template.code = code

        # Check file code before modifications
        self.assertTrue(
            self.file.code == code,
            msg="File code must be the same "
            "as template code before any modifications",
        )
        # Check file rendered code before modifications
        self.assertTrue(
            self.file.rendered_code == code,
            msg="File rendered code must be the same"
            " as template code before any modifications",
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

    def test_modify_template_related_files(self):
        # Create side effect for file write method
        # to track if method was called during
        # the test

        side_effect_target = {"write_called": False}

        def side_effect(this, vals):
            side_effect_target["write_called"] = True
            return False

        # patch file write method with side effect
        with patch.object(self.registry["cx.tower.file"], "write", side_effect):
            # Modify template name to see if it won't trigger
            # write method of the file
            self.file_template.name = "New name"
            self.assertFalse(
                side_effect_target["write_called"],
                msg=(
                    "File write method should not be called "
                    "after modifying template name."
                ),
            )

            # Modify template code to see if it will trigger
            # write method of the file
            self.file_template.code = "New code"
            self.assertTrue(
                side_effect_target["write_called"],
                msg="File write method should be called after modifying template code.",
            )

    def test_create_file_with_template(self):
        """
        Test if file is created with template code
        """
        file_template = self.env["cx.tower.file.template"].create(
            {
                "name": "Test",
                "file_name": "test.txt",
                "server_dir": "/var/tmp",
                "code": "Hello, world!",
            }
        )

        file = file_template.create_file(server=self.server_test_1)
        self.assertEqual(file.code, self.file_template.code)
        self.assertEqual(file.template_id, file_template)
        self.assertEqual(file.server_id, self.server_test_1)
        self.assertEqual(file.source, "tower")
        self.assertEqual(file.server_dir, self.file_template.server_dir)

        with self.assertRaises(exceptions.ValidationError):
            file_template.create_file(server=self.server_test_1, raise_if_exists=True)

        another_file = file_template.create_file(
            server=self.server_test_1, raise_if_exists=False
        )
        self.assertEqual(another_file, file)

    def test_create_file_with_template_custom_server_dir(self):
        """
        Test if file is created with template code and custom server dir
        """
        file_template = self.env["cx.tower.file.template"].create(
            {
                "name": "Test",
                "file_name": "test.txt",
                "server_dir": "/var/tmp",
                "code": "Hello, world!",
            }
        )

        file = file_template.create_file(
            server=self.server_test_1, server_dir="/var/tmp/custom"
        )
        self.assertEqual(file.code, self.file_template.code)
        self.assertEqual(file.template_id, file_template)
        self.assertEqual(file.server_id, self.server_test_1)
        self.assertEqual(file.source, "tower")
        self.assertEqual(file.server_dir, "/var/tmp/custom")

        with self.assertRaises(exceptions.ValidationError):
            file_template.create_file(
                server=self.server_test_1,
                server_dir="/var/tmp/custom",
                raise_if_exists=True,
            )

        another_file = file_template.create_file(
            server=self.server_test_1,
            server_dir="/var/tmp/custom",
            raise_if_exists=False,
        )
        self.assertEqual(another_file, file)
