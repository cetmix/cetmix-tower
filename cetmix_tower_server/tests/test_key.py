from odoo.exceptions import AccessError, ValidationError

from .common import TestTowerCommon


class TestTowerKey(TestTowerCommon):
    """Test class for tower key."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Create another manager for testing
        cls.manager_2 = cls.Users.create(
            {
                "name": "Second Manager",
                "login": "manager2",
                "email": "manager2@test.com",
                "groups_id": [(4, cls.env.ref("cetmix_tower_server.group_manager").id)],
            }
        )

        # Create test servers
        cls.server_1 = cls.Server.create(
            {
                "name": "Test Server 1",
                "ip_v4_address": "192.168.1.1",
                "ssh_port": 22,
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
            }
        )
        cls.server_2 = cls.Server.create(
            {
                "name": "Test Server 2",
                "ip_v4_address": "192.168.1.2",
                "ssh_port": 22,
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
            }
        )
        cls.test_key = cls.Key.create(
            {"name": "Test Key", "key_type": "s", "secret_value": "test value"}
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
        doge_key = self.Key.create(
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
        self.KeyValue.create(
            {
                "key_id": doge_key.id,
                "secret_value": "Doge partner",
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
        self.KeyValue.create(
            {
                "key_id": doge_key.id,
                "secret_value": "Doge server",
                "server_id": self.server_test_1.id,
            }
        )
        key_value = self.Key._parse_key_string(key_string, **kwargs)

        # Test server and partner specific key
        self.KeyValue.create(
            {
                "key_id": doge_key.id,
                "secret_value": "Doge server and partner",
                "server_id": self.server_test_1.id,
                "partner_id": self.user_bob.partner_id.id,
            }
        )
        key_value = self.Key._parse_key_string(key_string, **kwargs)
        self.assertEqual(
            key_value, "Doge server and partner", "Key value doesn't match"
        )

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
        doge_key = self.Key.create(
            {
                "name": "doge key",
                "reference": "DOGE_KEY",
                "key_type": "s",
            }
        )

        # 1. Test server and partner specific key
        server_partner_value = self.KeyValue.create(
            {
                "key_id": doge_key.id,
                "secret_value": "Doge server and partner",
                "server_id": self.server_test_1.id,
                "partner_id": self.user_bob.partner_id.id,
            }
        )
        kwargs = {
            "partner_id": self.user_bob.partner_id.id,
            "server_id": self.server_test_1.id,
        }
        key_value = self.Key._resolve_key_type_secret("DOGE_KEY", **kwargs)
        self.assertEqual(
            key_value, "Doge server and partner", "Key value doesn't match"
        )

        # 2. Global key
        doge_key.write({"secret_value": "Doge dog"})
        key_value = self.Key._resolve_key_type_secret("DOGE_KEY")
        self.assertEqual(key_value, "Doge dog", "Key value doesn't match")

        # 3. Non existing key
        key_value = self.Key._resolve_key_type_secret("PEPE_KEY")
        self.assertIsNone(key_value, "Key value must be 'None'")

        # 4. Partner specific key
        self.KeyValue.create(
            {
                "key_id": doge_key.id,
                "secret_value": "Doge partner",
                "partner_id": self.user_bob.partner_id.id,
            }
        )
        kwargs = {
            "partner_id": self.user_bob.partner_id.id,
        }
        key_value = self.Key._resolve_key_type_secret("DOGE_KEY", **kwargs)
        self.assertEqual(key_value, "Doge partner", "Key value doesn't match")

        # 5. Test server specific key
        self.KeyValue.create(
            {
                "key_id": doge_key.id,
                "secret_value": "Doge server",
                "server_id": self.server_test_1.id,
            }
        )
        kwargs = {
            "server_id": self.server_test_1.id,
        }
        key_value = self.Key._resolve_key_type_secret("DOGE_KEY", **kwargs)
        self.assertEqual(key_value, "Doge server", "Key value doesn't match")

        # 6. Test with non matching partner. Should return server specific value
        kwargs = {
            "partner_id": self.user.partner_id.id,
            "server_id": self.server_test_1.id,
        }
        key_value = self.Key._resolve_key_type_secret("DOGE_KEY", **kwargs)
        self.assertEqual(key_value, "Doge server", "Key value doesn't match")

        # 7. Change partner in the server-partner specific value.
        # Should return server specific value
        server_partner_value.write({"partner_id": self.manager.partner_id.id})
        kwargs = {
            "server_id": self.server_test_1.id,
        }
        key_value = self.Key._resolve_key_type_secret("DOGE_KEY", **kwargs)
        self.assertEqual(key_value, "Doge server", "Key value doesn't match")

        # 8. Test with the global key again
        key_value = self.Key._resolve_key_type_secret("DOGE_KEY")
        self.assertEqual(key_value, "Doge dog", "Key value doesn't match")

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
        code_parsed_expected = "Don't mess with None He will make you cry"
        expected_key_values = []
        check_parsed_code(code, code_parsed_expected, expected_key_values)

        check_parsed_code(code, code_parsed_expected)

        # 4 - Multi keys
        # Create new key
        doge_key = self.Key.create(
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
        self.KeyValue.create(
            {
                "key_id": doge_key.id,
                "secret_value": "Doge wow",
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
        self.KeyValue.create(
            {
                "key_id": doge_key.id,
                "secret_value": "Doge much",
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
        placeholder = self.Key.SECRET_VALUE_PLACEHOLDER
        expected_code = (
            f"Hey {placeholder} & Doge {placeholder} so "
            f"like {placeholder}!\n"
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
        """Test that regular users have no access to keys"""
        user_key = self.Key.with_user(self.user)

        # Create test key
        key = self.Key.create(
            {"name": "Test Key", "secret_value": "test value", "key_type": "s"}
        )

        # Test CRUD operations
        with self.assertRaises(AccessError):
            user_key.create(
                {"name": "New Key", "secret_value": "secret", "key_type": "s"}
            )
        with self.assertRaises(AccessError):
            user_key.browse(key.id).read(["name"])
        with self.assertRaises(AccessError):
            user_key.browse(key.id).write({"name": "Updated Name"})
        with self.assertRaises(AccessError):
            user_key.browse(key.id).unlink()

    def test_manager_read_access(self):
        """Test manager read access rules"""
        manager_key = self.Key.with_user(self.manager)

        # Create test keys
        key_secret = self.Key.create(
            {"name": "Secret Key", "secret_value": "secret value", "key_type": "s"}
        )
        key_ssh = self.Key.create(
            {"name": "SSH Key", "secret_value": "ssh key", "key_type": "k"}
        )

        # Test read access for secret key - should read (all managers can read secrets)
        self.assertTrue(manager_key.search([("id", "=", key_secret.id)]))

        # Test read access for SSH key without server access - should not find
        self.assertFalse(manager_key.search([("id", "=", key_ssh.id)]))

        # Add manager to server users and set SSH key - should find SSH key
        self.write_and_invalidate(
            self.server_1,
            **{"user_ids": [(4, self.manager.id)], "ssh_key_id": key_ssh.id},
        )
        self.assertTrue(manager_key.search([("id", "=", key_ssh.id)]))

        # Remove key from server - should not find again
        self.server_1.write({"ssh_key_id": False})
        self.assertFalse(manager_key.search([("id", "=", key_ssh.id)]))

        # Add as key user - should find both
        key_secret.write({"user_ids": [(4, self.manager.id)]})
        key_ssh.write({"user_ids": [(4, self.manager.id)]})
        self.assertTrue(manager_key.search([("id", "=", key_secret.id)]))
        self.assertTrue(manager_key.search([("id", "=", key_ssh.id)]))

    def test_manager_write_access(self):
        """Test manager write/create access rules"""
        manager_key = self.Key.with_user(self.manager)

        # Create test keys as root and ensure manager is not in manager_ids
        key_secret = self.Key.create(
            {
                "name": "Secret Key",
                "secret_value": "secret value",
                "key_type": "s",
                "manager_ids": [(5, 0)],  # Clear manager_ids
            }
        )
        key_ssh = self.Key.create(
            {
                "name": "SSH Key",
                "secret_value": "ssh key",
                "key_type": "k",
                "manager_ids": [(5, 0)],  # Clear manager_ids
            }
        )

        # Try write without being manager - should fail
        with self.assertRaises(AccessError):
            manager_key.browse(key_secret.id).write({"name": "Updated Secret"})
        with self.assertRaises(AccessError):
            manager_key.browse(key_ssh.id).write({"name": "Updated SSH"})

        # Add as key manager - should write to secret
        key_secret.write({"manager_ids": [(4, self.manager.id)]})
        manager_key.browse(key_secret.id).write({"name": "Updated Secret"})
        self.assertEqual(key_secret.name, "Updated Secret")

        # Add as server manager and set SSH key - should write to SSH key
        self.server_1.write(
            {"manager_ids": [(4, self.manager.id)], "ssh_key_id": key_ssh.id}
        )
        manager_key.browse(key_ssh.id).write({"name": "Updated SSH"})
        self.assertEqual(key_ssh.name, "Updated SSH")

    def test_manager_create_access(self):
        """Test manager create access rules"""
        manager_key = self.Key.with_user(self.manager)
        manager_2_key = self.Key.with_user(self.manager_2)

        # Try create secret key when not a manager - should fail
        with self.assertRaises(AccessError):
            manager_2_key.create(
                {
                    "name": "New Secret",
                    "secret_value": "secret",
                    "key_type": "s",
                    "manager_ids": [(5, 0)],  # Prevent automatic manager addition
                }
            )

        # Try create SSH key when not a server manager - should fail
        with self.assertRaises(AccessError):
            manager_2_key.create(
                {
                    "name": "New SSH",
                    "secret_value": "ssh key",
                    "key_type": "k",
                    "manager_ids": [(5, 0)],  # Prevent automatic manager addition
                }
            )

        # Add as server manager - should create SSH key
        self.server_1.write({"manager_ids": [(4, self.manager.id)]})
        new_ssh_key = manager_key.create(
            {"name": "New SSH", "secret_value": "ssh key", "key_type": "k"}
        )
        # Link key to server
        self.server_1.write({"ssh_key_id": new_ssh_key.id})
        self.assertTrue(new_ssh_key.exists())

    def test_manager_unlink_access(self):
        """Test manager unlink access rules"""
        manager_key = self.Key.with_user(self.manager)

        # Create keys as root
        key_secret = self.Key.create(
            {"name": "Secret Key", "secret_value": "secret value", "key_type": "s"}
        )
        key_ssh = self.Key.create(
            {"name": "SSH Key", "secret_value": "ssh key", "key_type": "k"}
        )
        # Link SSH key to server
        self.server_1.write({"ssh_key_id": key_ssh.id})

        # Try delete without being manager and creator - should fail
        with self.assertRaises(AccessError):
            manager_key.browse(key_secret.id).unlink()
        with self.assertRaises(AccessError):
            manager_key.browse(key_ssh.id).unlink()

        # Add as manager but not creator - should still fail
        key_secret.write({"manager_ids": [(4, self.manager.id)]})
        self.server_1.write({"manager_ids": [(4, self.manager.id)]})
        with self.assertRaises(AccessError):
            manager_key.browse(key_secret.id).unlink()
        with self.assertRaises(AccessError):
            manager_key.browse(key_ssh.id).unlink()

        # Create own keys - should delete
        own_secret = manager_key.create(
            {
                "name": "Own Secret",
                "secret_value": "secret",
                "key_type": "s",
                "manager_ids": [(4, self.manager.id)],
            }
        )
        own_ssh = manager_key.create(
            {"name": "Own SSH", "secret_value": "ssh key", "key_type": "k"}
        )
        # Link own SSH key to server
        self.server_1.write({"ssh_key_id": own_ssh.id})

        own_secret.unlink()
        own_ssh.unlink()
        self.assertFalse(own_secret.exists())
        self.assertFalse(own_ssh.exists())

    def test_root_access(self):
        """Test root access rules"""
        root_key = self.Key.with_user(self.root)

        # Create
        key = root_key.create(
            {"name": "Root Key", "secret_value": "root secret", "key_type": "s"}
        )
        self.assertTrue(key.exists())

        # Read
        self.assertEqual(root_key.browse(key.id).name, "Root Key")

        # Write
        root_key.browse(key.id).write({"name": "Updated Root Key"})
        self.assertEqual(key.name, "Updated Root Key")

        # Delete
        key.unlink()
        self.assertFalse(key.exists())

    def test_key_value_user_access(self):
        """Test that regular users have no access to key values"""
        user_key_value = self.KeyValue.with_user(self.user)

        # Create test key and key value
        key = self.Key.create({"name": "Test Key", "key_type": "s"})
        key_value = self.KeyValue.create(
            {"key_id": key.id, "secret_value": "test value"}
        )

        # Test CRUD operations
        with self.assertRaises(AccessError):
            user_key_value.create({"key_id": key.id, "secret_value": "new value"})
        with self.assertRaises(AccessError):
            user_key_value.browse(key_value.id).read(["secret_value"])
        with self.assertRaises(AccessError):
            user_key_value.browse(key_value.id).write({"secret_value": "updated value"})
        with self.assertRaises(AccessError):
            user_key_value.browse(key_value.id).unlink()

    def test_key_value_manager_read_access(self):
        """Test manager read access rules for key values"""
        manager_key_value = self.KeyValue.with_user(self.manager)

        # Create test key and key values
        key = self.Key.create({"name": "Test Key", "key_type": "s"})
        global_value = self.KeyValue.create(
            {"key_id": key.id, "secret_value": "global value"}
        )
        server_value = self.KeyValue.create(
            {
                "key_id": key.id,
                "secret_value": "server value",
                "server_id": self.server_1.id,
            }
        )

        # Test read access - should not find without proper access
        self.assertTrue(manager_key_value.search([("id", "=", global_value.id)]))
        self.assertFalse(manager_key_value.search([("id", "=", server_value.id)]))

        # Add as key user - should find global value and server value for that key
        key.write({"user_ids": [(4, self.manager.id)]})
        self.assertTrue(manager_key_value.search([("id", "=", global_value.id)]))
        self.assertTrue(manager_key_value.search([("id", "=", server_value.id)]))

        # Remove from key users
        key.write({"user_ids": [(3, self.manager.id)]})
        self.assertTrue(manager_key_value.search([("id", "=", global_value.id)]))
        self.assertFalse(manager_key_value.search([("id", "=", server_value.id)]))

        # Add as server user - should find server value
        self.server_1.write({"user_ids": [(4, self.manager.id)]})
        self.assertTrue(manager_key_value.search([("id", "=", global_value.id)]))
        self.assertTrue(manager_key_value.search([("id", "=", server_value.id)]))

    def test_key_value_manager_write_access(self):
        """Test manager write/create access rules for key values"""
        manager_key_value = self.KeyValue.with_user(self.manager)

        # Create test key and key values
        key = self.Key.create({"name": "Test Key", "key_type": "s"})
        global_value = self.KeyValue.create(
            {"key_id": key.id, "secret_value": "global value"}
        )
        server_value = self.KeyValue.create(
            {
                "key_id": key.id,
                "secret_value": "server value",
                "server_id": self.server_1.id,
            }
        )

        # Try write without proper access - should fail
        with self.assertRaises(AccessError):
            manager_key_value.browse(global_value.id).write(
                {"secret_value": "new value"}
            )
        with self.assertRaises(AccessError):
            manager_key_value.browse(server_value.id).write(
                {"secret_value": "new value"}
            )

        # Add as key manager - should write to global value
        key.write({"manager_ids": [(4, self.manager.id)]})
        manager_key_value.browse(global_value.id).write(
            {"secret_value": "updated global"}
        )
        self.assertEqual(
            global_value._get_secret_value("secret_value"), "updated global"
        )

        # Add as server manager - should write to server value
        self.server_1.write({"manager_ids": [(4, self.manager.id)]})
        manager_key_value.browse(server_value.id).write(
            {"secret_value": "updated server"}
        )
        self.assertEqual(
            server_value._get_secret_value("secret_value"), "updated server"
        )

        # Test create access
        for_bob = manager_key_value.create(
            {
                "key_id": key.id,
                "secret_value": "for bob",
                "partner_id": self.user_bob.partner_id.id,
            }
        )
        self.assertTrue(for_bob.exists())

    def test_key_value_manager_unlink_access(self):
        """Test manager unlink access rules for key values"""
        manager_key_value = self.KeyValue.with_user(self.manager)

        # Create test key and key values
        key = self.Key.create({"name": "Test Key", "key_type": "s"})

        # Create values as root
        global_value = self.KeyValue.create(
            {"key_id": key.id, "secret_value": "global value"}
        )
        server_value = self.KeyValue.create(
            {
                "key_id": key.id,
                "secret_value": "server value",
                "server_id": self.server_1.id,
            }
        )

        # Try delete without proper access - should fail
        with self.assertRaises(AccessError):
            manager_key_value.browse(global_value.id).unlink()
        with self.assertRaises(AccessError):
            manager_key_value.browse(server_value.id).unlink()

        # Add as manager but not creator - should still fail
        key.write({"manager_ids": [(4, self.manager.id)]})
        self.server_1.write({"manager_ids": [(4, self.manager.id)]})
        with self.assertRaises(AccessError):
            manager_key_value.browse(global_value.id).unlink()
        with self.assertRaises(AccessError):
            manager_key_value.browse(server_value.id).unlink()

        # Create own values - should delete
        own_partner_value = manager_key_value.create(
            {
                "key_id": key.id,
                "secret_value": "own partner",
                "partner_id": self.user_bob.partner_id.id,
            }
        )

        # Unlink server value first to avoid constraint error
        server_value.unlink()

        # Create server value
        own_server_value = manager_key_value.create(
            {
                "key_id": key.id,
                "secret_value": "own server",
                "server_id": self.server_1.id,
            }
        )

        own_partner_value.unlink()
        own_server_value.unlink()
        self.assertFalse(own_partner_value.exists())
        self.assertFalse(own_server_value.exists())

    def test_key_value_root_access(self):
        """Test root access rules for key values"""
        root_key_value = self.KeyValue.with_user(self.root)

        # Create test key
        key = self.Key.create({"name": "Test Key", "key_type": "s"})

        # Create
        value = root_key_value.create({"key_id": key.id, "secret_value": "root value"})
        self.assertTrue(value.exists())

        # Read
        self.assertEqual(
            root_key_value.browse(value.id)._get_secret_value("secret_value"),
            "root value",
        )

        # Write
        root_key_value.browse(value.id).write({"secret_value": "updated value"})
        self.assertEqual(value._get_secret_value("secret_value"), "updated value")

        # Delete
        value.unlink()
        self.assertFalse(value.exists())

    def test_key_value_global_unique(self):
        """Test global value uniqueness"""

        # Try to create a value for the same key
        with self.assertRaises(ValidationError):
            another_global_value = self.KeyValue.create(
                {"key_id": self.test_key.id, "secret_value": "another test value"}
            )
            #
            another_global_value.unlink()

    def test_key_value_server_unique(self):
        """Test server value uniqueness"""
        # Create server tight value

        self.KeyValue.create(
            {
                "key_id": self.test_key.id,
                "secret_value": "server related",
                "server_id": self.server_1.id,
            }
        )

        # Try create another value for the same server
        with self.assertRaises(ValidationError):
            self.KeyValue.create(
                {
                    "key_id": self.test_key.id,
                    "secret_value": "another server related",
                    "server_id": self.server_1.id,
                }
            )

    def test_key_value_partner_unique(self):
        """Test partner value uniqueness"""
        # Create partner tight value
        self.KeyValue.create(
            {
                "key_id": self.test_key.id,
                "secret_value": "partner related",
                "partner_id": self.user_bob.partner_id.id,
            }
        )

        # Try create another value for the same partner
        with self.assertRaises(ValidationError):
            self.KeyValue.create(
                {
                    "key_id": self.test_key.id,
                    "secret_value": "another partner related",
                    "partner_id": self.user_bob.partner_id.id,
                }
            )

    def test_key_value_server_partner_unique(self):
        """Test server and partner value uniqueness"""

        # Create server and partner tight value
        self.KeyValue.create(
            {
                "key_id": self.test_key.id,
                "secret_value": "server related",
                "server_id": self.server_1.id,
                "partner_id": self.user_bob.partner_id.id,
            }
        )

        # Try create another value for the same server and partner
        with self.assertRaises(ValidationError):
            self.KeyValue.create(
                {
                    "key_id": self.test_key.id,
                    "secret_value": "another server related",
                    "server_id": self.server_1.id,
                    "partner_id": self.user_bob.partner_id.id,
                }
            )
