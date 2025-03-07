from odoo.exceptions import AccessError

from .common import TestTowerCommon


class TestTowerKey(TestTowerCommon):
    """Test class for tower key."""

    def setUp(self, *args, **kwargs):
        super().setUp(*args, **kwargs)
        # Create another manager for testing
        self.manager_2 = self.Users.create(
            {
                "name": "Second Manager",
                "login": "manager2",
                "email": "manager2@test.com",
                "groups_id": [
                    (4, self.env.ref("cetmix_tower_server.group_manager").id)
                ],
            }
        )

        # Create test servers
        self.server_1 = self.Server.create(
            {
                "name": "Test Server 1",
                "ip_v4_address": "192.168.1.1",
                "ssh_port": 22,
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
            }
        )
        self.server_2 = self.Server.create(
            {
                "name": "Test Server 2",
                "ip_v4_address": "192.168.1.2",
                "ssh_port": 22,
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
            }
        )

    def test_key_creation(self):
        """
        Test key creation.
        We override create method so need to check if reference is generated properly
        """

        # -- 1--
        #  Check new key values
        key_one = self.Key.create(
            {"name": " test key meme   ", "secret_value": "test value", "key_type": "s"}
        )
        self.assertEqual(
            key_one.reference, "test_key_meme", "Reference must be 'test_key_meme'"
        )
        self.assertEqual(
            key_one.name,
            "test key meme",
            "Trailing and leading whitespaces must be removed from name",
        )

    def test_key_access_rights(self):
        """Test private key security features"""

        # Default message returned instead of key value
        SECRET_VALUE_PLACEHOLDER = self.Key.SECRET_VALUE_PLACEHOLDER

        # Store key value
        self.write_and_invalidate(
            self.key_1, **{"secret_value": "pepe", "key_type": "s"}
        )

        # Get key value as Bob
        key_bob = self.key_1.with_user(self.user_bob)

        with self.assertRaises(AccessError):
            key_value = key_bob.secret_value

        # Add user to group
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        # Add user to server
        self.server_test_1.write({"user_ids": [(4, self.user_bob.id)]})
        # Add server to key
        self.write_and_invalidate(self.key_1, **{"server_id": self.server_test_1.id})

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

        # Add Bob to Root group and test write again
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_root")
        self.write_and_invalidate(key_bob, **{"secret_value": "frog"})

        # Read with context and check if secret value is returned
        key_with_context = self.key_1.with_context(show_secret_value=True)
        key_value = key_with_context.secret_value
        self.assertEqual(key_value, "frog", msg="Must return key value 'frog'")

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
                "reference": "DOGE_KEY",
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
                "reference": "DOGE_KEY",
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
                "reference": "DOGE_KEY",
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
                "reference": "DOGE_KEY",
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
                "reference": "DOGE_KEY",
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
                "reference": "DOGE_KEY",
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
                "reference": "DOGE_KEY",
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
                "reference": "MEME_KEY",
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
                "reference": "DOGE_KEY",
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
                "reference": "DOGE_KEY",
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
                "reference": "DOGE_KEY",
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

    def test_user_access(self):
        """Test that regular users have no access"""
        Key = self.env["cx.tower.key"].with_user(self.user)

        # Try to read - should fail with access error
        with self.assertRaises(AccessError):
            Key.search([])

        # Try to create - should fail
        with self.assertRaises(AccessError):
            Key.create(
                {
                    "name": "User Key",
                    "key_type": "k",
                    "secret_value": "user_key",
                }
            )

        # Try to write - should fail
        with self.assertRaises(AccessError):
            self.key_1.with_user(self.user).write({"name": "New Name"})

        # Try to unlink - should fail
        with self.assertRaises(AccessError):
            self.key_1.with_user(self.user).unlink()

    def test_manager_read_ssh_key(self):
        """Test manager read access for SSH keys"""
        Key = self.env["cx.tower.key"].with_user(self.manager)

        # Create SSH key with server reference
        ssh_key = self.Key.create(
            {
                "name": "Test SSH Key",
                "key_type": "k",
                "secret_value": "test_key",
            }
        )
        # Link SSH key to server
        self.server_test_1.write({"ssh_key_id": ssh_key.id})

        # No access initially
        self.assertFalse(Key.search([("id", "=", ssh_key.id)]))

        # Add as user - should read
        self.server_test_1.write({"user_ids": [(4, self.manager.id)]})
        self.assertTrue(Key.search([("id", "=", ssh_key.id)]))

        # Remove user, add as manager - should read
        self.server_test_1.write(
            {
                "user_ids": [(3, self.manager.id)],
                "manager_ids": [(4, self.manager.id)],
            }
        )
        self.assertTrue(Key.search([("id", "=", ssh_key.id)]))

        # Remove manager, add as user to key - should read
        ssh_key.write({"user_ids": [(4, self.manager.id)]})
        self.assertTrue(Key.search([("id", "=", ssh_key.id)]))

        # Remove  user, add as manager to key - should read
        ssh_key.write(
            {"manager_ids": [(4, self.manager.id)], "user_ids": [(3, self.manager.id)]}
        )
        self.assertTrue(Key.search([("id", "=", ssh_key.id)]))

    def test_manager_read_secret(self):
        """Test manager read access for secrets"""
        Key = self.env["cx.tower.key"].with_user(self.manager)

        # Create secret
        secret = self.Key.create(
            {
                "name": "Test Secret",
                "key_type": "s",
                "secret_value": "test_secret",
                "server_id": self.server_1.id,
            }
        )

        # No access initially
        self.assertFalse(Key.search([("id", "=", secret.id)]))

        # Add as user - should read
        self.server_1.write({"user_ids": [(4, self.manager.id)]})
        self.assertTrue(Key.search([("id", "=", secret.id)]))

        # Remove user, add as manager - should read
        self.server_1.write(
            {
                "user_ids": [(3, self.manager.id)],
                "manager_ids": [(4, self.manager.id)],
            }
        )
        self.assertTrue(Key.search([("id", "=", secret.id)]))

    def test_manager_write_ssh_key(self):
        """Test manager write/create access for SSH keys"""
        Key = self.env["cx.tower.key"].with_user(self.manager)

        # Try create without server access - should fail
        with self.assertRaises(AccessError):
            Key.create(
                {
                    "name": "Manager SSH Key",
                    "key_type": "k",
                    "secret_value": "manager_key",
                    "user_ids": [],
                    "manager_ids": [],
                }
            )

        # Add manager to server
        self.server_test_1.write({"manager_ids": [(4, self.manager.id)]})

        # Create SSH key and link to server - should succeed
        ssh_key = Key.create(
            {
                "name": "Manager SSH Key",
                "key_type": "k",
                "secret_value": "manager_key",
            }
        ).with_context(show_secret_value=True)
        self.server_test_1.write({"ssh_key_id": ssh_key.id})

        # Write - should succeed
        self.write_and_invalidate(ssh_key, **{"secret_value": "updated_key"})
        self.assertEqual(ssh_key.secret_value, "updated_key")

        # Remove manager from server and add as manager to key
        # Should succeed
        self.server_test_1.write({"manager_ids": [(3, self.manager.id)]})
        ssh_key.write({"manager_ids": [(4, self.manager.id)]})
        self.write_and_invalidate(ssh_key, **{"secret_value": "updated_key_2"})
        self.assertEqual(ssh_key.secret_value, "updated_key_2")

    def test_manager_write_secret(self):
        """Test manager write/create access for secrets"""
        Key = self.env["cx.tower.key"].with_user(self.manager)

        # Add manager to server
        self.server_1.write({"manager_ids": [(4, self.manager.id)]})

        # Create secret - should succeed
        secret = Key.create(
            {
                "name": "Manager Secret",
                "key_type": "s",
                "secret_value": "manager_secret",
                "server_id": self.server_1.id,
            }
        ).with_context(show_secret_value=True)
        self.assertTrue(secret.exists())

        # Write - should succeed
        self.write_and_invalidate(secret, **{"secret_value": "updated_secret"})
        self.assertEqual(secret.secret_value, "updated_secret")

        # Try write to secret of another server - should fail
        other_secret = self.Key.create(
            {
                "name": "Other Secret",
                "key_type": "s",
                "secret_value": "other_secret",
                "server_id": self.server_2.id,
            }
        ).with_context(show_secret_value=True)
        with self.assertRaises(AccessError):
            other_secret.with_user(self.manager).write({"secret_value": "try_update"})

    def test_manager_unlink(self):
        """Test manager unlink access"""
        # Add manager_2 to server first
        self.server_test_1.write({"manager_ids": [(4, self.manager_2.id)]})

        # Create keys as manager_2
        Key = self.env["cx.tower.key"].with_user(self.manager_2)

        # Create SSH key and link to server
        ssh_key = Key.create(
            {
                "name": "Manager SSH Key",
                "key_type": "k",
                "secret_value": "manager_ssh_key",
            }
        )
        self.server_test_1.write({"ssh_key_id": ssh_key.id})

        # Create secret
        secret = Key.create(
            {
                "name": "Manager Secret",
                "key_type": "s",
                "secret_value": "manager_secret",
                "server_id": self.server_test_1.id,
            }
        )

        # Try delete as different manager - should fail
        self.server_test_1.write({"manager_ids": [(4, self.manager.id)]})
        with self.assertRaises(AccessError):
            ssh_key.with_user(self.manager).unlink()
        with self.assertRaises(AccessError):
            secret.with_user(self.manager).unlink()

        # Delete own keys - should succeed
        ssh_key.with_user(self.manager_2).unlink()
        secret.with_user(self.manager_2).unlink()
        self.assertFalse(ssh_key.exists())
        self.assertFalse(secret.exists())

    def test_root_access(self):
        """Test root access"""
        Key = self.env["cx.tower.key"].with_user(self.root)

        # Create
        ssh_key = Key.create(
            {
                "name": "Root SSH Key",
                "key_type": "k",
                "secret_value": "root_ssh_key",
            }
        )
        secret = Key.create(
            {
                "name": "Root Secret",
                "key_type": "s",
                "secret_value": "root_secret",
                "server_id": self.server_1.id,
            }
        )
        self.assertTrue(ssh_key.exists())
        self.assertTrue(secret.exists())

        # Read
        self.assertTrue(Key.search([]))

        # Write
        ssh_key.write({"secret_value": "updated_ssh_key"})
        secret.write({"secret_value": "updated_secret"})
        self.assertEqual(ssh_key.secret_value, "updated_ssh_key")
        self.assertEqual(secret.secret_value, "updated_secret")

        # Delete
        ssh_key.unlink()
        secret.unlink()
        self.assertFalse(ssh_key.exists())
        self.assertFalse(secret.exists())
