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
