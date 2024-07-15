from odoo.exceptions import AccessError

from .common import TestTowerCommon


class TestTowerKey(TestTowerCommon):
    def setUp(self, *args, **kwargs):
        super().setUp(*args, **kwargs)

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

    def test_extract_key_strings(self):
        """Check if key strings are extracted properly"""
        code = (
            "Hey #!cxtower.secret.MEME_KEY!# & Doge #!cxtower.secret.DOGE_KEY !# so "
            "like #!cxtower.secret.MEME_KEY!#!\n"
            "They make #!memes together."
            "And this is another string for the same #!cxtower.secret.MEME_KEY  !#"
        )
        key_strings = self.Key._extract_key_strings(code)
        self.assertEqual(len(key_strings), 3, "Must be 3 key stings")
        self.assertIn(
            "#!cxtower.secret.MEME_KEY!#",
            key_strings,
            "Key string must be in key strings",
        )
        self.assertIn(
            "#!cxtower.secret.DOGE_KEY !#",
            key_strings,
            "Key string must be in key strings",
        )
        self.assertIn(
            "#!cxtower.secret.MEME_KEY  !#",
            key_strings,
            "Key string must be in key strings",
        )

    def test_parse_key_string(self):
        """Check if key string is parsed correctly"""

        # Test global key
        self.Key.create(
            {
                "name": "doge key",
                "key_ref": "DOGE_KEY",
                "secret_value": "Doge dog",
                "key_type": "s",
            }
        )
        key_string = "#!cxtower.secret.DOGE_KEY!#"
        key_value = self.Key._parse_key_string(key_string)
        self.assertEqual(key_value, "Doge dog", "Key value doesn't match")

        # Test the same key string but with some spaces before the key terminator
        key_string = "#!cxtower.secret.DOGE_KEY  !#"
        key_value = self.Key._parse_key_string(key_string)
        self.assertEqual(key_value, "Doge dog", "Key value doesn't match")

        # Test partner specific key
        self.Key.create(
            {
                "name": "doge key",
                "key_ref": "DOGE_KEY",
                "secret_value": "Doge partner",
                "key_type": "s",
                "partner_id": self.user_bob.partner_id.id,
            }
        )
        # compose kwargs
        kwargs = {
            "partner_id": self.user_bob.partner_id.id,
            "server_id": self.server_test_1.id,
        }
        key_value = self.Key._parse_key_string(key_string, **kwargs)
        self.assertEqual(key_value, "Doge partner", "Key value doesn't match")

        # Test server specific key
        self.Key.create(
            {
                "name": "doge key",
                "key_ref": "DOGE_KEY",
                "secret_value": "Doge server",
                "key_type": "s",
                "partner_id": self.user_bob.partner_id.id,
                "server_id": self.server_test_1.id,
            }
        )
        key_value = self.Key._parse_key_string(key_string, **kwargs)
        self.assertEqual(key_value, "Doge server", "Key value doesn't match")

        # Test missing key
        key_string = "#!cxtower.secret.ANOTHER_KEY!#"
        key_value = self.Key._parse_key_string(key_string)
        self.assertIsNone(key_value, "Key value must be 'None'")

        # Test missformatted key
        key_string = "#!cxtower.ANOTHER_KEY!#"
        key_value = self.Key._parse_key_string(key_string)
        self.assertIsNone(key_value, "Key value must be 'None'")

        # Test another missformatted key
        key_string = "#!cxtower.notasecret.DOGE_KEY!#"
        key_value = self.Key._parse_key_string(key_string)
        self.assertIsNone(key_value, "Key value must be 'None'")

    def test_resolve_key(self):
        """Check generic key resolver"""
        self.Key.create(
            {
                "name": "doge key",
                "key_ref": "DOGE_KEY",
                "secret_value": "Doge dog",
                "key_type": "s",
            }
        )

        # Existing key
        key_value = self.Key._resolve_key("secret", "DOGE_KEY")
        self.assertEqual(key_value, "Doge dog", "Key value doesn't match")

        # Non existing key
        key_value = self.Key._resolve_key("server", "PEPE_KEY")
        self.assertIsNone(key_value, "Key value must be 'None'")

    def test_resolve_key_type_secret(self):
        """Check 'secret' type key resolver"""
        self.Key.create(
            {
                "name": "doge key",
                "key_ref": "DOGE_KEY",
                "secret_value": "Doge dog",
                "key_type": "s",
            }
        )

        # Existing key
        key_value = self.Key._resolve_key_type_secret("DOGE_KEY")
        self.assertEqual(key_value, "Doge dog", "Key value doesn't match")

        # Non existing key
        key_value = self.Key._resolve_key_type_secret("PEPE_KEY")
        self.assertIsNone(key_value, "Key value must be 'None'")

        # Test partner specific key
        self.Key.create(
            {
                "name": "doge key",
                "key_ref": "DOGE_KEY",
                "secret_value": "Doge partner",
                "key_type": "s",
                "partner_id": self.user_bob.partner_id.id,
            }
        )
        # compose kwargs
        kwargs = {
            "partner_id": self.user_bob.partner_id.id,
            "server_id": self.server_test_1.id,
        }
        key_value = self.Key._resolve_key_type_secret("DOGE_KEY", **kwargs)
        self.assertEqual(key_value, "Doge partner", "Key value doesn't match")

        # Test server specific key
        self.Key.create(
            {
                "name": "doge key",
                "key_ref": "DOGE_KEY",
                "secret_value": "Doge server",
                "key_type": "s",
                "partner_id": self.user_bob.partner_id.id,
                "server_id": self.server_test_1.id,
            }
        )
        key_value = self.Key._resolve_key_type_secret("DOGE_KEY", **kwargs)
        self.assertEqual(key_value, "Doge server", "Key value doesn't match")

    def test_parse_code(self):
        """Test code parsing"""

        def check_parsed_code(
            code, code_parsed_expected, expected_key_values=None, **kwargs
        ):
            """Helper function for code parse testing

            Args:
                code (Text): code to parse
                code_parsed_expected (Text): expected parsed code
                expected_key_values (list, optional): key values that are expected
                 to be returned. Defaults to None.
            """
            code_parsed = self.Key._parse_code(code, **kwargs)
            self.assertEqual(
                code_parsed,
                code_parsed_expected,
                msg="Parsed code doesn't match expected one",
            )
            if expected_key_values:
                result = self.Key._parse_code_and_return_key_values(code, **kwargs)
                code_parsed = result["code"]
                key_values = result["key_values"]
                self.assertEqual(
                    code_parsed,
                    code_parsed_expected,
                    msg="Parsed code doesn't match expected one",
                )
                self.assertEqual(
                    len(key_values),
                    len(expected_key_values),
                    "Number of key values doesn't match number of expected ones",
                )
                for expected_value in expected_key_values:
                    self.assertIn(
                        expected_value,
                        key_values,
                        f"Value {expected_value} must be in the returned key values",
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

        code = "The key to understand this meme is #!cxtower.secret.MEME_KEY!#"
        code_parsed_expected = "The key to understand this meme is Pepe Frog"
        expected_key_values = ["Pepe Frog"]
        check_parsed_code(code, code_parsed_expected, expected_key_values)

        # 2 - multi line
        code = "Welcome #!cxtower.secret.MEME_KEY!#\nNew hero of this city!"
        code_parsed_expected = "Welcome Pepe Frog\nNew hero of this city!"
        expected_key_values = ["Pepe Frog"]
        check_parsed_code(code, code_parsed_expected, expected_key_values)

        # 3 - Key not found
        code = "Don't mess with #!cxtower.secret.DOGE_LIKE!# He will make you cry"
        code_parsed_expected = (
            "Don't mess with #!cxtower.secret.DOGE_LIKE!# He will make you cry"
        )
        expected_key_values = []
        check_parsed_code(code, code_parsed_expected, expected_key_values)

        check_parsed_code(code, code_parsed_expected)

        # 4 - Multi keys
        # Create new key
        self.Key.create(
            {
                "name": "doge key",
                "key_ref": "DOGE_KEY",
                "secret_value": "Doge dog",
                "key_type": "s",
            }
        )
        code = (
            "Hey #!cxtower.secret.MEME_KEY!# & Doge #!cxtower.secret.DOGE_KEY !# so "
            "like #!cxtower.secret.MEME_KEY!#!\n"
            "They make #!memes together. Check #!cxtower.secret.MEME_KEY&#!"
            "cxtower.secret.DOGE_KEY"
        )
        code_parsed_expected = (
            "Hey Pepe Frog & Doge Doge dog so "
            "like Pepe Frog!\n"
            "They make #!memes together. Check #!cxtower.secret.MEME_KEY&#!"
            "cxtower.secret.DOGE_KEY"
        )
        expected_key_values = ["Pepe Frog", "Doge dog"]
        check_parsed_code(code, code_parsed_expected, expected_key_values)

        # 5 - Partner specific key
        # Create new key for partner Bob
        self.Key.create(
            {
                "name": "doge key",
                "key_ref": "DOGE_KEY",
                "secret_value": "Doge wow",
                "key_type": "s",
                "partner_id": self.user_bob.partner_id.id,
            }
        )
        # compose kwargs
        kwargs = {"partner_id": self.user_bob.partner_id.id}
        code_parsed_expected = (
            "Hey Pepe Frog & Doge Doge wow so "
            "like Pepe Frog!\n"
            "They make #!memes together. Check #!cxtower.secret.MEME_KEY&#!"
            "cxtower.secret.DOGE_KEY"
        )
        expected_key_values = ["Pepe Frog", "Doge wow"]
        check_parsed_code(code, code_parsed_expected, expected_key_values, **kwargs)

        # 6 - Server specific key
        # Create new key for server Test 1
        self.Key.create(
            {
                "name": "doge key",
                "key_ref": "DOGE_KEY",
                "secret_value": "Doge much",
                "key_type": "s",
                "partner_id": self.user_bob.partner_id.id,  # not needed but may keep it
                "server_id": self.server_test_1.id,
            }
        )
        # compose kwargs
        kwargs = {
            "partner_id": self.user_bob.partner_id.id,  # not needed but may keep it
            "server_id": self.server_test_1.id,
        }
        code_parsed_expected = (
            "Hey Pepe Frog & Doge Doge much so "
            "like Pepe Frog!\n"
            "They make #!memes together. Check #!cxtower.secret.MEME_KEY&#!"
            "cxtower.secret.DOGE_KEY"
        )
        expected_key_values = ["Pepe Frog", "Doge much"]
        check_parsed_code(code, code_parsed_expected, expected_key_values, **kwargs)

    def test_replace_with_spoiler(self):
        """Check if secrets are replaced with spoiler correctly"""

        code = (
            "Hey Pepe Frog & Doge Doge much so "
            "like Pepe Frog!\n"
            "They make #!memes together. Check #!cxtower.secret.MEME_KEY&#!"
            "cxtower.secret.DOGE_KEY"
        )
        expected_code = (
            f"Hey {self.Key.SECRET_VALUE_SPOILER} & Doge {self.Key.SECRET_VALUE_SPOILER} so "  # noqa
            f"like {self.Key.SECRET_VALUE_SPOILER}!\n"
            "They make #!memes together. Check #!cxtower.secret.MEME_KEY&#!"
            "cxtower.secret.DOGE_KEY"
        )
        key_values = ["Pepe Frog", "Doge much"]

        result = self.Key._replace_with_spoiler(code, key_values)
        self.assertEqual(result, expected_code, "Result doesn't match expected code")

        # --------------------------------------
        # Check with some random key values now
        # Original code should rename unchanged
        # --------------------------------------

        key_values = ["Wow much", "No like"]
        result = self.Key._replace_with_spoiler(code, key_values)
        self.assertEqual(result, code, "Result doesn't match expected code")
