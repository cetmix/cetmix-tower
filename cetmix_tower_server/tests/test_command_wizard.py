from odoo.exceptions import AccessError, ValidationError

from .common import TestTowerCommon


class TestTowerCommandWizard(TestTowerCommon):
    def test_user_access_rules(self):
        """Test user access rules"""

        # Add Bob to `root` group in order to create a wizard
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_root")

        # Create new wizard
        test_wizard = (
            self.env["cx.tower.command.execute.wizard"]
            .with_user(self.user_bob)
            .create(
                {
                    "server_ids": [self.server_test_1.id],
                    "command_id": self.command_create_dir.id,
                }
            )
        ).with_user(self.user_bob)

        # Force rendered code computation
        test_wizard._compute_rendered_code()

        # Remove bob from all cxtower_server groups
        self.remove_from_group(
            self.user_bob,
            [
                "cetmix_tower_server.group_user",
                "cetmix_tower_server.group_manager",
                "cetmix_tower_server.group_root",
            ],
        )
        # Ensure that regular user cannot execute command in wizard
        with self.assertRaises(AccessError):
            test_wizard.execute_command_in_wizard()

        # Add bob back to `user` group and try again
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")
        with self.assertRaises(AccessError):
            test_wizard.execute_command_in_wizard()

        # Now promote bob to `manager` group and try again
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        test_wizard.execute_command_in_wizard()

    def test_execute_code_without_a_command(self):
        """Execute command code without a command selected"""

        # Add Bob to `root` group in order to create a wizard
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_root")

        # Create new wizard
        test_wizard = (
            self.env["cx.tower.command.execute.wizard"]
            .with_user(self.user_bob)
            .create(
                {
                    "server_ids": [self.server_test_1.id],
                }
            )
        ).with_user(self.user_bob)

        # Should not allow to run command on server if no command is selected
        with self.assertRaises(ValidationError):
            test_wizard.execute_command_on_server()

    def test_execute_command_on_server_access_rights(self):
        """Test access rights for executing command on server"""

        # Add Bob to `root` group
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_root")

        # Create new wizard with Bob as a root user
        test_wizard = (
            self.env["cx.tower.command.execute.wizard"]
            .with_user(self.user_bob)
            .create(
                {
                    "server_ids": [self.server_test_1.id],
                    "command_id": self.command_create_dir.id,
                }
            )
        ).with_user(self.user_bob)

        # Ensure command can be executed by root
        test_wizard.execute_command_on_server()

        # Remove Bob from all tower server groups
        self.remove_from_group(
            self.user_bob,
            [
                "cetmix_tower_server.group_user",
                "cetmix_tower_server.group_manager",
                "cetmix_tower_server.group_root",
            ],
        )

        # Ensure that regular user cannot execute command on server
        with self.assertRaises(AccessError):
            test_wizard.execute_command_on_server()

        #  Add Bob to `user` group and ensure he can execute commands
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")
        test_wizard.execute_command_on_server()
        # Ensure that Bob has access to path field but can't read its value
        allowed_path = (
            self.user_bob.has_group("cetmix_tower_server.group_manager")
            and test_wizard.path
        )

        self.assertEqual(allowed_path, False)
        # Ensure that Bob can write to the path field as a member of `group_user`
        # the result will be None
        test_wizard.write({"path": "/new/invalid/path"})
        allowed_path = (
            test_wizard.path
            if self.user_bob.has_group("cetmix_tower_server.group_manager")
            and test_wizard.path
            else None
        )
        self.assertEqual(allowed_path, None)

        # Add Bob to `manager` group and ensure access to execute commands
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        test_wizard.execute_command_on_server()
        # Check that path access is valid for the manager
        test_wizard.read(["path"])
