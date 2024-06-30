from odoo.exceptions import AccessError

from .common import TestTowerCommon


class TestTowerlog(TestTowerCommon):
    def test_user_access_rule(self):
        """Test user access rule"""
        # Create the test command
        test_command_log = self.CommandLog.create(
            {
                "server_id": self.server_test_1.id,
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
        # Ensure that regular user cannot access the command log
        test_command_log_as_bob = test_command_log.with_user(self.user_bob)
        with self.assertRaises(AccessError):
            command_name = test_command_log_as_bob.read(["name"])

        # Add user_bob to group user
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")
        # Ensure that user still doesn't have access to command log he did't create
        with self.assertRaises(AccessError):
            command_name = test_command_log_as_bob.read(["name"])
        # Add user_bob to group manager
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        # Ensure that manager doesn't have access to command belongs to server
        #  he did't subscribed to
        with self.assertRaises(AccessError):
            command_name = test_command_log_as_bob.read(["name"])
        # Subscribe manager to server and test again
        self.server_test_1.message_subscribe([self.user_bob.partner_id.id])
        command_name = test_command_log_as_bob.read(["name"])
        self.assertEqual(
            command_name[0]["name"],
            test_command_log_as_bob.name,
            "Command name should be same",
        )

        # Check if user Bob can unlink command_log entry as member of group_manager
        with self.assertRaises(
            AccessError,
            msg="member of group_manager should \
                                not be able to unlink log entries",
        ):
            test_command_log_as_bob.unlink()

        # Create a new command
        test_command_1 = self.Command.create(
            {
                "name": "Test",
                "code": "ls",
                "access_level": "1",
            }
        )

        # Create a new command log as user_bob
        test_command_log_1 = self.CommandLog.create(
            {
                "server_id": self.server_test_1.id,
                "command_id": test_command_1.id,
                "create_uid": self.user_bob.id,
            }
        )

        # Remove user_bob from group_manager
        self.remove_from_group(
            self.user_bob,
            [
                "cetmix_tower_server.group_manager",
            ],
        )
        # Ensure that user_bob has access to test_command_log_1
        command_name_1 = test_command_log_1.with_user(self.user_bob).read(["name"])
        self.assertEqual(
            command_name_1[0]["name"],
            test_command_log_1.name,
            "Command name should be same",
        )
        # Update test_command access_level to "2"
        test_command_1.write({"access_level": "2"})
        # Ensure that user_bob doesn't have access to test_command_log_1 anymore
        with self.assertRaises(AccessError):
            command_name = test_command_log_1.with_user(self.user_bob).read(["name"])
