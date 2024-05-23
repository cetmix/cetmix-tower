from odoo.exceptions import AccessError

from .common import TestTowerCommon


class TestTowerPlanlog(TestTowerCommon):
    def test_user_access_rule(self):
        """Test user access rule"""
        # Create the test command
        test_plan_log = self.PlanLog.create(
            {
                "server_id": self.server_test_1.id,
                "plan_id": self.plan_1.id,
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
        test_plan_log_as_bob = test_plan_log.with_user(self.user_bob)
        test_plan_log_as_bob.invalidate_cache()
        with self.assertRaises(AccessError):
            plan_name = test_plan_log_as_bob.read(["name"])

        # Add user_bob to group user
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")
        # Ensure that user still doesn't have access to command he did't create
        with self.assertRaises(AccessError):
            plan_name = test_plan_log_as_bob.read(["name"])

        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        # Ensure that manager doesn't have access to command belongs to server
        #  he did't subscribed to
        with self.assertRaises(AccessError):
            plan_name = test_plan_log_as_bob.read(["name"])
        # Subscibe manager to server and test again
        self.server_test_1.message_subscribe([self.user_bob.partner_id.id])
        plan_name = test_plan_log_as_bob.read(["name"])
        self.assertEqual(
            plan_name[0]["name"],
            test_plan_log_as_bob.name,
            "Plan name should be same",
        )

        # Check if user Bob can unlink command_log entry as member of group_manager
        with self.assertRaises(
            AccessError,
            msg="member of group_manager should \
                                not be able to unlink log entries",
        ):
            test_plan_log_as_bob.unlink()
