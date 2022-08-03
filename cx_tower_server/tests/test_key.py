from odoo.exceptions import AccessError, ValidationError

from .test_common import TestTowerCommon


class TestTowerKey(TestTowerCommon):
    def test_key_access_rights(self):
        """Test private key security features"""

        # Default message returned instead of key value
        key_placeholder = self.Key.KEY_PLACEHOLDER

        # Store key value
        self.write_and_invalidate(self.key_1, **{"ssh_key": "pepe"})

        # Get key value as Bob
        key_bob = self.key_1.with_user(self.user_bob)

        with self.assertRaises(AccessError):
            key_value = key_bob.ssh_key

        # Add user to group
        self.add_to_group(self.user_bob, "cx_tower_server.group_user")

        # Get value
        key_value = key_bob.ssh_key

        # Ensure placeholder is used instead of the key value
        self.assertEqual(
            key_value,
            key_placeholder,
            msg="Must return placeholder '{}'".format(key_placeholder),
        )

        # Test write
        with self.assertRaises(AccessError):
            self.write_and_invalidate(key_bob, **{"ssh_key": "frog"})

        # Add Bob to Manager group and test write again
        self.add_to_group(self.user_bob, "cx_tower_server.group_manager")
        self.write_and_invalidate(key_bob, **{"ssh_key": "frog"})

        # Read as sudo and check if the value is updated
        key_sudo = self.key_1.sudo()
        key_value = key_sudo.ssh_key
        self.assertEqual(key_value, "frog", msg="Must return key value 'frog'")

        # Try deleting key. Should raise access error
        with self.assertRaises(AccessError):
            key_bob.unlink()

        # Add Bob to Root group and test write again
        self.add_to_group(self.user_bob, "cx_tower_server.group_root")
        key_bob.unlink()

    def test_key_constraints(self):
        """Test private key security features"""

        # Store key value
        self.write_and_invalidate(self.key_1, **{"ssh_key": "pepe"})

        # Try creating another key with the same value. Must raise validation error
        with self.assertRaises(ValidationError):
            self.Key.create({"name": "Second key", "ssh_key": "pepe"})

        # Must be ok if value differs
        second_key = self.Key.create({"name": "Second key", "ssh_key": "frog"})
        self.assertEqual(
            second_key.sudo().ssh_key, "frog", msg="Must return key value 'frog'"
        )
