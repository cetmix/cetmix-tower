from odoo.exceptions import AccessError, ValidationError

from .test_common import TestTowerCommon


class TestTowerKey(TestTowerCommon):
    def test_key_access_rights(self):
        """Test private key security features"""

        # Default message returned instead of key value
        SECRET_VALUE_PLACEHOLDER = self.Key.SECRET_VALUE_PLACEHOLDER

        # Store key value
        self.write_and_invalidate(self.key_1, **{"secret_value": "pepe"})

        # Get key value as Bob
        key_bob = self.key_1.with_user(self.user_bob)

        with self.assertRaises(AccessError):
            key_value = key_bob.secret_value

        # Add user to group
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")

        # Get value
        key_value = key_bob.secret_value

        # Ensure placeholder is used instead of the key value
        self.assertEqual(
            key_value,
            SECRET_VALUE_PLACEHOLDER,
            msg="Must return placeholder '{}'".format(SECRET_VALUE_PLACEHOLDER),
        )

        # Test write
        with self.assertRaises(AccessError):
            self.write_and_invalidate(key_bob, **{"secret_value": "frog"})

        # Add Bob to Manager group and test write again
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        self.write_and_invalidate(key_bob, **{"secret_value": "frog"})

        # Read as sudo and check if the value is updated
        key_sudo = self.key_1.sudo()
        key_value = key_sudo.secret_value
        self.assertEqual(key_value, "frog", msg="Must return key value 'frog'")

        # Try deleting key. Should raise access error
        with self.assertRaises(AccessError):
            key_bob.unlink()

        # Add Bob to Root group and test write again
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_root")
        key_bob.unlink()

    def test_key_constraints(self):
        """Test private key security features"""

        # Store key value
        self.write_and_invalidate(self.key_1, **{"secret_value": "pepe"})

        # Try creating another key with the same value. Must raise validation error
        with self.assertRaises(ValidationError):
            self.Key.create({"name": "Second key", "secret_value": "pepe"})

        # Must be ok if value differs
        second_key = self.Key.create({"name": "Second key", "secret_value": "frog"})
        self.assertEqual(
            second_key.sudo().secret_value, "frog", msg="Must return key value 'frog'"
        )

    def test_key_inline_keys(self):
        """Inline keys in code"""

        def check_parsed_code(code, code_parsed_expected):
            """Helper function to check parsed code"""
            code_parsed = self.Key.parse_code(code)
            self.assertEqual(
                code_parsed,
                code_parsed_expected,
                msg="Parsed code doesn't match expected one",
            )

        # Create new key
        self.Key.create(
            {
                "name": "Meme key",
                "key_ref": "MEME_KEY",
                "secret_value": "Pepe Frog",
                "key_type": "s",
            }
        )

        # Check key parser

        # 1 - single line

        code = "The key to understand this meme is #!cxtower.secret.MEME_KEY"
        code_parsed_expected = "The key to understand this meme is Pepe Frog"
        check_parsed_code(code, code_parsed_expected)

        # 2 - multi line
        code = "Welcome #!cxtower.secret.MEME_KEY\nNew hero of this city!"
        code_parsed_expected = "Welcome Pepe Frog\nNew hero of this city!"
        check_parsed_code(code, code_parsed_expected)

        # 3 - Key not found
        code = "Don't mess with #!cxtower.secret.DOGE_LIKE He will make you cry"
        code_parsed_expected = "Don't mess with  He will make you cry"
        check_parsed_code(code, code_parsed_expected)

        # 4 - Key terminated explicitly with '!#'
        code = "Don't mess with #!cxtower.secret.MEME_KEY!#! He will make you cry"
        code_parsed_expected = "Don't mess with Pepe Frog! He will make you cry"
        check_parsed_code(code, code_parsed_expected)

        # 5 - Multi keys
        # Create new key
        self.Key.create(
            {
                "name": "doge key",
                "key_ref": "DOGE_KEY",
                "secret_value": "Doge",
                "key_type": "s",
            }
        )
        code = (
            "#!cxtower.secret.DOGE_KEY so like #!cxtower.secret.MEME_KEY!#!\n"
            "They make #!memes together. Check #!cxtower.secret.MEME_KEY&#!"
            "cxtower.secret.DOGE_KEY"
        )
        code_parsed_expected = (
            "Doge so like Pepe Frog!\nThey make #!memes together. Check "
        )
        check_parsed_code(code, code_parsed_expected)
