from odoo import exceptions
from odoo.exceptions import AccessError

from .common import TestTowerCommon


class TestTowerFile(TestTowerCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.file_template = cls.FileTemplate.create(
            {
                "name": "Test",
                "file_name": "test.txt",
                "server_dir": "/var/tmp",
                "code": "Hello, world!",
            }
        )
        cls.file = cls.File.create(
            {
                "name": "tower_demo_1.txt",
                "source": "tower",
                "template_id": cls.file_template.id,
                "server_id": cls.server_test_1.id,
            }
        )
        cls.file_2 = cls.File.create(
            {
                "name": "test.txt",
                "source": "server",
                "server_id": cls.server_test_1.id,
                "server_dir": "/var/tmp",
            }
        )

        # Create a dummy Server record that will be referenced by file records.
        cls.server = cls.Server.create(
            {
                "name": "Test Server",
                "manager_ids": [(6, 0, [cls.manager.id])],
                "user_ids": [(6, 0, [cls.user.id])],
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "skip_host_key": True,
                "os_id": cls.os_debian_10.id,
                "ip_v4_address": "localhost",
            }
        )

    def test_user_read_access(self):
        """
        Test that a user in the custom User group can read a file record
        when their ID is in the related server's user_ids.
        """
        file_record = self.File.create(
            {
                "name": "Test File",
                "server_dir": "/tmp",
                "file_type": "text",
                "source": "tower",
                "server_id": self.server.id,
            }
        )
        # As the user, the file record should be visible.
        files_for_user = self.File.with_user(self.user).search(
            [("id", "=", file_record.id)]
        )
        self.assertTrue(
            files_for_user,
            "User should be able to read the file record "
            "because they are in server.user_ids.",
        )

        # Remove user from server.user_ids.
        self.server.write({"user_ids": [(3, self.user.id)]})
        files_for_user = self.File.with_user(self.user).search(
            [("id", "=", file_record.id)]
        )
        self.assertFalse(
            files_for_user,
            "User should not be able to read the file record "
            "because he is not in server.user_ids.",
        )

    def test_manager_write_create_access(self):
        """
        Test that a manager in the custom Manager group can create and write
        file records when his ID is in the related server's manager_ids.
        """
        # Test creation: the manager is in server.manager_ids.
        file_record = self.File.with_user(self.manager).create(
            {
                "name": "Manager Created File",
                "server_dir": "/tmp",
                "file_type": "text",
                "source": "tower",
                "server_id": self.server.id,
            }
        )
        self.assertTrue(
            file_record,
            "Manager should be able to create a file record "
            "because they are in server.manager_ids.",
        )

        # Test updating (write access).
        try:
            file_record.with_user(self.manager).write({"name": "Manager Updated File"})
        except AccessError:
            self.fail(
                "Manager should be able to update the file record "
                "because he is in server.manager_ids."
            )
        self.assertEqual(
            file_record.with_user(self.manager).name,
            "Manager Updated File",
            "File record name should be updated by the manager.",
        )

        # Test that a manager who is not in the server's manager_ids
        # cannot write or create.
        # Remove manager from server.manager_ids.
        self.server.write({"manager_ids": [(3, self.manager.id)]})
        # Create a file record on this server.
        file_record2 = self.File.create(
            {
                "name": "File on Server Without Manager",
                "server_dir": "/tmp",
                "file_type": "text",
                "source": "tower",
                "server_id": self.server.id,
            }
        )
        with self.assertRaises(AccessError):
            file_record2.with_user(self.manager).write({"name": "Should Not Update"})

        # Test create access for a manager not in manager_ids.
        with self.assertRaises(AccessError):
            self.File.with_user(self.manager).create(
                {
                    "name": "Invalid File",
                    "server_dir": "/tmp",
                    "file_type": "text",
                    "source": "tower",
                    "server_id": self.server.id,
                }
            )

    def test_manager_unlink_access(self):
        """
        Test that a manager in the custom Manager group can unlink (delete) a file
        record only if he is in the related server's manager_ids
        and they are the record's creator.
        """
        # Scenario 1: Record created by the manager.
        file_record = self.File.with_user(self.manager).create(
            {
                "name": "File to Delete",
                "server_dir": "/tmp",
                "file_type": "text",
                "source": "tower",
                "server_id": self.server.id,
            }
        )
        try:
            file_record.with_user(self.manager).unlink()
        except AccessError:
            self.fail(
                "Manager should be able to delete their own file"
                " record when in server.manager_ids."
            )

        # Scenario 2: Record created by someone else (e.g., the admin).
        file_record2 = self.File.create(
            {
                "name": "File Not Deletable by Manager",
                "server_dir": "/tmp",
                "file_type": "text",
                "source": "tower",
                "server_id": self.server.id,
            }
        )
        with self.assertRaises(AccessError):
            file_record2.with_user(self.manager).unlink()

    def test_upload_file(self):
        """
        Upload file from tower to server
        """
        self.file.action_push_to_server()
        self.assertEqual(self.file.server_response, "ok")

    def test_delete_file(self):
        """
        Delete file remotely from server
        """
        result = self.file.action_delete_from_server()
        self.assertTrue(isinstance(result, dict))
        self.assertEqual(result["params"]["message"], "File deleted!")

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
        self.file_2.action_pull_from_server()
        self.assertEqual(self.file_2.code, "ok")

        self.file_2.name = "binary.zip"
        res = self.file_2.action_pull_from_server()
        self.assertTrue(
            isinstance(res, dict) and res["tag"] == "display_notification",
            msg=(
                "If file type is 'binary', then the result must be a dict "
                "representing the display_notification action."
            ),
        )

    def test_get_current_server_code(self):
        """
        Download file from server to tower
        """
        self.file.action_push_to_server()
        self.assertEqual(self.file.server_response, "ok")

        self.file.action_get_current_server_code()
        self.assertEqual(self.file.code_on_server, "ok")

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
        self.file.action_unlink_from_template()

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
        """
        Check that after change file template
        all related files will update
        """
        self.assertEqual(self.file_template.file_name, "test.txt")
        # related files
        self.assertTrue(
            all(file.name == "test.txt" for file in self.file_template.file_ids)
        )

        # update file template name
        self.file_template.file_name = "new_test.txt"
        # Related files must updated
        self.assertTrue(
            all(file.name == "new_test.txt" for file in self.file_template.file_ids)
        )

        self.assertEqual(self.file_template.code, "Hello, world!")
        # update file template code
        self.file_template.code = "New code"
        # Related files must updated
        self.assertTrue(
            all(file.code == "New code" for file in self.file_template.file_ids)
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

        file = file_template.create_file(
            server=self.server_test_1,
            server_dir=file_template.server_dir,
            if_file_exists="overwrite",
        )
        self.assertEqual(file.code, self.file_template.code)
        self.assertEqual(file.template_id, file_template)
        self.assertEqual(file.server_id, self.server_test_1)
        self.assertEqual(file.source, "tower")
        self.assertEqual(file.server_dir, self.file_template.server_dir)

        with self.assertRaises(exceptions.ValidationError):
            file_template.create_file(
                server=self.server_test_1,
                server_dir=file_template.server_dir,
                if_file_exists="raise",
            )

        another_file = file_template.create_file(
            server=self.server_test_1,
            server_dir=file_template.server_dir,
            if_file_exists="skip",
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
                if_file_exists="raise",
            )

        another_file = file_template.create_file(
            server=self.server_test_1,
            server_dir="/var/tmp/custom",
            if_file_exists="skip",
        )
        self.assertEqual(another_file, file)

    def test_file_with_secret_key(self):
        """
        Test case to verify that when a file includes a secret reference,
        the secret key is automatically linked with the file.
        """

        # Create a secret key
        secret_python_key = self.Key.create(
            {
                "name": "python",
                "reference": "PYTHON",
                "secret_value": "secretPythonCode",
                "key_type": "s",
            }
        )

        # Create a file template with a reference to the secret key
        file_template = self.env["cx.tower.file.template"].create(
            {
                "name": "Test",
                "file_name": "test.txt",
                "server_dir": "/var/tmp",
                "code": "Please use this secret #!cxtower.secret.PYTHON!#",
            }
        )

        # Create a file from the file template
        file = file_template.create_file(
            server=self.server_test_1, server_dir="/var/tmp/custom"
        )

        # Assert that the file's code matches the file template's code
        self.assertEqual(
            file.code,
            file_template.code,
            msg="The file's code does not match the file template's code.",
        )

        # Assert that the secret key is associated with the file
        self.assertIn(
            secret_python_key,
            file.secret_ids,
            msg="The secret key is not associated with the file.",
        )

        # Update the file's code to remove the secret reference
        file.code = "Only text"

        self.assertFalse(
            file.secret_ids,
            msg=(
                "The secret_ids field should be empty after "
                "removing the secret reference from file."
            ),
        )

    def test_file_with_sensitive_variable(self):
        """
        Test case to verify that user has access to use file with sensitive variables.
        """
        # Create file with sensitive variable
        file = self.File.create(
            {
                "source": "tower",
                "name": "test.txt",
                "server_id": self.server_test_1.id,
                "code": "'IPv4 Address': {{ tower.server.ipv4 }}",
            }
        )
        # Remove user_bob from all cx_tower_server groups
        self.remove_from_group(
            self.user_bob,
            [
                "cetmix_tower_server.group_user",
                "cetmix_tower_server.group_manager",
                "cetmix_tower_server.group_root",
            ],
        )
        # Add bob to user group
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")
        # Add bob as subscriber of the server to allow upload file
        self.server_test_1.write({"user_ids": [(4, self.user_bob.id)]})
        # Upload file to server
        self.assertTrue(file.server_response != "ok")
        file.with_user(self.user_bob).action_push_to_server()
        self.assertEqual(file.server_response, "ok")

    def test_sanitize_values(self):
        """
        Test case to verify that the sanitize_values method works correctly.
        """
        # 1. Root directory
        values = self.File._sanitize_values({"server_dir": "/"})
        self.assertEqual(values["server_dir"], "/")

        # 2. Trailing slash
        values = self.File._sanitize_values({"server_dir": "/var/tmp/"})
        self.assertEqual(values["server_dir"], "/var/tmp")

        # 3. Trailing whitespace
        values = self.File._sanitize_values({"server_dir": "/var/tmp/ "})
        self.assertEqual(values["server_dir"], "/var/tmp")

        # 4. Leading whitespace
        values = self.File._sanitize_values({"server_dir": " /var/tmp/"})
        self.assertEqual(values["server_dir"], "/var/tmp")

        # 5. Leading and trailing whitespace
        values = self.File._sanitize_values({"server_dir": " /var/tmp/ "})
        self.assertEqual(values["server_dir"], "/var/tmp")

        # 6. Leading and trailing whitespace just one slash
        values = self.File._sanitize_values({"server_dir": " / "})
        self.assertEqual(values["server_dir"], "/")
