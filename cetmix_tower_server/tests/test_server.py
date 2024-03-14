from odoo.exceptions import AccessError

from .common import TestTowerCommon


class TestTowerServer(TestTowerCommon):
    def test_server_access_rights(self):
        """Test Server access rights"""

        # Bob is a regular user with no access to Servers
        server_1_as_bob = self.server_test_1.with_user(self.user_bob)

        # Invalidating cache so values will be fetched again with access check applied
        server_1_as_bob.invalidate_cache()

        # Access error should be raised because user has no access to the model
        with self.assertRaises(AccessError):
            server_name = server_1_as_bob.name

        # Add user to group
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")
        server_name = server_1_as_bob.name
        self.assertEqual(
            server_name, self.server_test_1.name, msg="Sever name does not match!"
        )

        # Test write
        with self.assertRaises(AccessError):
            self.write_and_invalidate(server_1_as_bob, **{"name": "New Server Name"})

        # Add Bob to Manager group and test write again
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        self.write_and_invalidate(server_1_as_bob, **{"name": "New Server Name"})

        # Read as sudo and check if the value is updated
