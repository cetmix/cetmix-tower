from odoo.exceptions import AccessError

from .common import TestTowerCommon


class TestTowerServerLog(TestTowerCommon):
    """Test server log model"""

    def setUp(self, *args, **kwargs):
        super().setUp(*args, **kwargs)

        # Crete a log from file of type 'server'
        file_for_log = self.File.create(
            {
                "source": "server",
                "name": "test.log",
                "server_dir": "/tmp",
                "server_id": self.server_test_1.id,
                "code": "Some log record - server",
            }
        )

        self.server_log_file_server = self.ServerLog.create(
            {
                "name": "Log from file",
                "server_id": self.server_test_1.id,
                "log_type": "file",
                "file_id": file_for_log.id,
            }
        )

        # Crete a log from file of type 'tower'
        file_for_log_tower = self.File.create(
            {
                "source": "tower",
                "name": "test_tower.log",
                "server_dir": "/tmp",
                "server_id": self.server_test_1.id,
                "code_on_server": "Some log record - tower",
            }
        )

        self.server_log_file_tower = self.ServerLog.create(
            {
                "name": "Log from file",
                "server_id": self.server_test_1.id,
                "log_type": "file",
                "file_id": file_for_log_tower.id,
            }
        )

        # Crete a log from command
        self.command_for_log = self.Command.create(
            {"name": "Get system info", "code": "uname -a"}
        )

        self.server_log_command = self.ServerLog.create(
            {
                "name": "Log from command",
                "server_id": self.server_test_1.id,
                "log_type": "command",
                "command_id": self.command_for_log.id,
            }
        )

    def test_user_access_rule(self):
        """Test user access rules"""

        # Ensure that default log access level is equal to 2
        self.assertEqual(self.server_log_command.access_level, "2")

        # Remove bob from all cxtower_server groups
        self.remove_from_group(
            self.user_bob,
            [
                "cetmix_tower_server.group_user",
                "cetmix_tower_server.group_manager",
                "cetmix_tower_server.group_root",
            ],
        )
        # Ensure that regular user cannot access the server log
        test_server_log_command_as_bob = self.server_log_command.with_user(
            self.user_bob
        )
        with self.assertRaises(AccessError):
            server_log_name = test_server_log_command_as_bob.name
        self.server_log_command.write({"access_level": "1"})

        # Add user to group
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")

        # Ensure that user still doesn't have read access
        # because he is not added as follower to the server
        with self.assertRaises(AccessError):
            server_log_name = test_server_log_command_as_bob.name

        # Add user as follower to the server
        self.server_test_1.message_subscribe(partner_ids=[self.user_bob.partner_id.id])

        # Ensure that user can access the server log
        server_log_name = test_server_log_command_as_bob.name
        self.assertEqual(
            server_log_name,
            self.server_log_command.name,
            msg=f"Must return '{self.server_log_command.name}'",
        )

        # Add user to group_manager
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")

        # Create a new server with access_level 1
        new_server_log_bob = self.ServerLog.with_user(self.user_bob).create(
            {
                "name": "Bob Server Log",
                "access_level": "1",
                "server_id": self.server_test_1.id,
                "log_type": "command",
                "command_id": self.command_create_dir.id,
            }
        )
        self.assertEqual(new_server_log_bob.access_level, "1")

        # Try to elevate the access_level of new_server_log_bob to 2
        new_server_log_bob.with_user(self.user_bob).write({"access_level": "2"})
        self.assertEqual(new_server_log_bob.access_level, "2")

        # Ensure that manager user cannot see commands with access_level 3
        server_log_root = self.ServerLog.create(
            {
                "name": "Restricted Server Log",
                "access_level": "3",
                "server_id": self.server_test_1.id,
                "log_type": "command",
                "command_id": self.command_create_dir.id,
            }
        )

        user_bob_records = self.ServerLog.with_user(self.user_bob).search([])
        user_bob_records_access_level_3 = user_bob_records.filtered(
            lambda r: r.access_level == "3"
        )
        self.assertFalse(user_bob_records_access_level_3, "Must return 0 records")

        # Add user to group_root
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_root")

        # Ensure that root user can see commands with access_level 3
        user_bob_records = self.ServerLog.with_user(self.user_bob).search([])
        user_bob_records_access_level_3 = user_bob_records.filtered(
            lambda r: r.access_level == "3"
        )
        self.assertTrue(user_bob_records_access_level_3, "Must not be empty")

        # Ensure root record is in the list
        self.assertIn(
            server_log_root,
            user_bob_records_access_level_3,
            "Record must be in the list",
        )

        # Try to demote the access_level of new_server_log_bob to 2
        server_log_root.with_user(self.user_bob).write({"access_level": "2"})
        self.assertEqual(server_log_root.access_level, "2")

        # Checking the case that may require clearing the cache:
        # Create a command with "Manager" access level.
        cc_server_log = self.ServerLog.create(
            {
                "name": "CC Server Log",
                "access_level": "2",
                "server_id": self.server_test_1.id,
                "log_type": "command",
                "command_id": self.command_create_dir.id,
            }
        )

        # Remove bob from all cxtower_server groups
        self.remove_from_group(
            self.user_bob,
            [
                "cetmix_tower_server.group_user",
                "cetmix_tower_server.group_manager",
                "cetmix_tower_server.group_root",
            ],
        )
        # Add user to group
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")
        # Check command list with "Tower-User" user. User cannot see this command.
        with self.assertRaises(AccessError):
            server_log_name = cc_server_log.with_user(self.user_bob).name
        # Change the server log access level to "User".
        cc_server_log.write({"access_level": "1"})

        server_log_name = cc_server_log.with_user(self.user_bob).name
        self.assertEqual(
            server_log_name, "CC Server Log", msg="Must return 'CC Server Log'"
        )

    def test_log_update(self):
        """Test log update results"""

        # ------------------------------
        # 1. Type: file, source: server
        # ------------------------------
        self.server_log_file_server.action_get_log_text()
        self.assertEqual(
            self.ServerLog._format_log_text(self.server_log_file_server.file_id.code),
            self.server_log_file_server.log_text,
            "Log text doesn't match expected one",
        )

        # ------------------------------
        # 2. Type: file, source: tower
        # ------------------------------
        self.server_log_file_tower.action_get_log_text()
        self.assertEqual(
            self.ServerLog._format_log_text(
                self.server_log_file_tower.file_id.code_on_server
            ),
            self.server_log_file_tower.log_text,
            "Log text doesn't match expected one",
        )
        # ------------------------------
        # 3. Type: command, source: tower
        # ------------------------------
        self.server_log_command.action_get_log_text()
        self.assertEqual(
            self.ServerLog._format_log_text("ok"),
            self.server_log_command.log_text,
            "Log text doesn't match expected one",
        )

    def test_log_update_all(self):
        """
        Test log update results when triggered all
        server logs of selected server.
        """

        # Trigger log update
        self.server_test_1.action_update_server_logs()

        # ------------------------------
        # 1. Type: file, source: server
        # ------------------------------
        self.assertEqual(
            self.ServerLog._format_log_text(self.server_log_file_server.file_id.code),
            self.server_log_file_server.log_text,
            "Log text doesn't match expected one",
        )

        # ------------------------------
        # 2. Type: file, source: tower
        # ------------------------------
        self.assertEqual(
            self.ServerLog._format_log_text(
                self.server_log_file_tower.file_id.code_on_server
            ),
            self.server_log_file_tower.log_text,
            "Log text doesn't match expected one",
        )
        # ------------------------------
        # 3. Type: command, source: tower
        # ------------------------------
        self.assertEqual(
            self.ServerLog._format_log_text("ok"),
            self.server_log_command.log_text,
            "Log text doesn't match expected one",
        )

    def test_log_update_all_restricted(self):
        """
        Test log update results when triggered all
        server logs of selected server.
        Using a user with restricted access level
        """

        # Remove bob from all cxtower_server groups
        self.remove_from_group(
            self.user_bob,
            [
                "cetmix_tower_server.group_user",
                "cetmix_tower_server.group_manager",
                "cetmix_tower_server.group_root",
            ],
        )
        # .. and add back to the "user" group
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")

        # Set access level for all logs to 'user'
        self.write_and_invalidate(self.server_log_command, **{"access_level": "1"})
        self.write_and_invalidate(self.server_log_file_server, **{"access_level": "1"})
        self.write_and_invalidate(self.server_log_file_tower, **{"access_level": "1"})

        # Increment command access level to 'root'
        self.write_and_invalidate(self.command_for_log, **{"access_level": "3"})

        # Ensure that Bob doesn't have direct access to command
        with self.assertRaises(AccessError):
            self.command_for_log.with_user(self.user_bob).read(["name"])

        # Trigger log update
        self.server_test_1.action_update_server_logs()

        # ------------------------------
        # 1. Type: file, source: server
        # ------------------------------
        self.assertEqual(
            self.ServerLog._format_log_text(self.server_log_file_server.file_id.code),
            self.server_log_file_server.log_text,
            "Log text doesn't match expected one",
        )

        # ------------------------------
        # 2. Type: file, source: tower
        # ------------------------------
        self.assertEqual(
            self.ServerLog._format_log_text(
                self.server_log_file_tower.file_id.code_on_server
            ),
            self.server_log_file_tower.log_text,
            "Log text doesn't match expected one",
        )
        # ------------------------------
        # 3. Type: command, source: tower
        # ------------------------------
        self.assertEqual(
            self.ServerLog._format_log_text("ok"),
            self.server_log_command.log_text,
            "Log text doesn't match expected one",
        )
