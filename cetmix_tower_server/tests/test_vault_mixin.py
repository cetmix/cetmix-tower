# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from .common import TestTowerCommon


class TestVaultMixin(TestTowerCommon):
    """Test vault mixin functionality."""

    def test_vault_mixin_secret_fields(self):
        """Test vault mixin functionality for secret fields
        (host_key and ssh_password)"""
        # Create a server with initial secret values
        initial_password = "initial_password"
        initial_host_key = "initial_host_key"

        server = self.Server.create(
            {
                "name": "Vault Test Server",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": initial_password,
                "ssh_auth_mode": "p",
                "os_id": self.os_debian_10.id,
                "host_key": initial_host_key,
                "skip_host_key": False,
            }
        )

        # Test 1: Verify initial values are stored in vault and accessible
        # Read values using common way - should return placeholder
        self.assertEqual(
            server.ssh_password,
            self.Server.SECRET_VALUE_PLACEHOLDER,
            "ssh_password should return placeholder value when read normally",
        )
        self.assertEqual(
            server.host_key,
            self.Server.SECRET_VALUE_PLACEHOLDER,
            "host_key should return placeholder value when read normally",
        )

        # Read using _get_secret_values() - should return actual initial values
        secret_values = server._get_secret_values()
        self.assertIsNotNone(secret_values, "secret_values should not be None")
        self.assertIn(server.id, secret_values, "Server ID should be in secret values")

        server_secrets = secret_values[server.id]
        self.assertIn(
            "ssh_password", server_secrets, "ssh_password should be in secret values"
        )
        self.assertIn("host_key", server_secrets, "host_key should be in secret values")

        self.assertEqual(
            server_secrets["ssh_password"],
            initial_password,
            "ssh_password should return initial value from vault",
        )
        self.assertEqual(
            server_secrets["host_key"],
            initial_host_key,
            "host_key should return initial value from vault",
        )

        # Read individual fields using _get_secret_value()
        # should return initial values
        retrieved_password = server._get_secret_value("ssh_password")
        retrieved_host_key = server._get_secret_value("host_key")

        self.assertEqual(
            retrieved_password,
            initial_password,
            "_get_secret_value should return correct initial ssh_password",
        )
        self.assertEqual(
            retrieved_host_key,
            initial_host_key,
            "_get_secret_value should return correct initial host_key",
        )

        # Test 2: Save new values to secret fields
        new_password = "new_secure_password_123"
        new_host_key = "new_host_key_456"

        server.write(
            {
                "ssh_password": new_password,
                "host_key": new_host_key,
            }
        )

        # Test 3: Read values using common way after update - should return placeholder
        # Note: In Odoo, we need to re-read the record to see updated values
        server = self.Server.browse(server.id)
        self.assertEqual(
            server.ssh_password,
            self.Server.SECRET_VALUE_PLACEHOLDER,
            "ssh_password should return placeholder value when read normally "
            "after update",
        )
        self.assertEqual(
            server.host_key,
            self.Server.SECRET_VALUE_PLACEHOLDER,
            "host_key should return placeholder value when read normally "
            "after update",
        )

        # Test 4: Read using _get_secret_values() after update
        # should return new values
        secret_values = server._get_secret_values()
        self.assertIsNotNone(
            secret_values, "secret_values should not be None after update"
        )
        self.assertIn(
            server.id,
            secret_values,
            "Server ID should be in secret values after update",
        )

        server_secrets = secret_values[server.id]
        self.assertIn(
            "ssh_password",
            server_secrets,
            "ssh_password should be in secret values after update",
        )
        self.assertIn(
            "host_key",
            server_secrets,
            "host_key should be in secret values after update",
        )

        self.assertEqual(
            server_secrets["ssh_password"],
            new_password,
            "ssh_password should return new value from vault after update",
        )
        self.assertEqual(
            server_secrets["host_key"],
            new_host_key,
            "host_key should return new value from vault after update",
        )

        # Test 5: Read individual fields using _get_secret_value() after update
        # Get both values in one call using _get_secret_values()
        secret_values = server._get_secret_values()
        self.assertIsNotNone(
            secret_values, "secret_values should not be None for individual field test"
        )
        self.assertIn(
            server.id,
            secret_values,
            "Server ID should be in secret values for individual field test",
        )

        server_secrets = secret_values[server.id]
        retrieved_password = server_secrets["ssh_password"]
        retrieved_host_key = server_secrets["host_key"]

        self.assertEqual(
            retrieved_password,
            new_password,
            "_get_secret_values should return correct new ssh_password after update",
        )
        self.assertEqual(
            retrieved_host_key,
            new_host_key,
            "_get_secret_values should return correct new host_key after update",
        )

        # Test 6: Verify that non-secret fields are not affected
        self.assertEqual(
            server.name,
            "Vault Test Server",
            "Non-secret field should not be affected by vault mixin",
        )
        self.assertEqual(
            server.ssh_username,
            "admin",
            "Non-secret field should not be affected by vault mixin",
        )

    def test_vault_mixin_create_with_secret_fields(self):
        """Test vault mixin functionality when creating records with secret fields"""
        # Create a server with secret fields
        server = self.Server.create(
            {
                "name": "Create Test Server",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "create_password",
                "ssh_auth_mode": "p",
                "os_id": self.os_debian_10.id,
                "host_key": "create_host_key",
                "skip_host_key": False,
            }
        )

        # Verify secret fields are stored in vault and not in main table
        self.assertEqual(
            server.ssh_password,
            self.Server.SECRET_VALUE_PLACEHOLDER,
            "ssh_password should return placeholder after creation",
        )
        self.assertEqual(
            server.host_key,
            self.Server.SECRET_VALUE_PLACEHOLDER,
            "host_key should return placeholder after creation",
        )

        # Verify actual values are accessible via vault methods
        secret_values = server._get_secret_values()
        self.assertIn(
            server.id,
            secret_values,
            "Server ID should be in secret values after creation",
        )

        server_secrets = secret_values[server.id]
        self.assertEqual(
            server_secrets["ssh_password"],
            "create_password",
            "ssh_password should be stored in vault after creation",
        )
        self.assertEqual(
            server_secrets["host_key"],
            "create_host_key",
            "host_key should be stored in vault after creation",
        )

    def test_vault_mixin_delete_secret_fields(self):
        """Test vault mixin functionality when deleting secret field values"""
        # Create a server with secret fields
        server = self.Server.create(
            {
                "name": "Delete Test Server",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "delete_password",
                "ssh_auth_mode": "p",
                "os_id": self.os_debian_10.id,
                "host_key": "delete_host_key",
                "skip_host_key": False,
            }
        )

        # Verify initial values exist
        secret_values = server._get_secret_values()
        self.assertIn(
            "ssh_password",
            secret_values[server.id],
            "ssh_password should exist initially",
        )
        self.assertIn(
            "host_key", secret_values[server.id], "host_key should exist initially"
        )

        # Delete secret field values
        server.write(
            {
                "ssh_password": False,
                "host_key": False,
            }
        )

        # Verify values are removed from vault
        secret_values = server._get_secret_values()
        server_secrets = secret_values.get(server.id, {})

        self.assertNotIn(
            "ssh_password", server_secrets, "ssh_password should be removed from vault"
        )
        self.assertNotIn(
            "host_key", server_secrets, "host_key should be removed from vault"
        )

        # Verify normal field access still returns placeholders
        server = self.Server.browse(server.id)
        self.assertEqual(
            server.ssh_password,
            self.Server.SECRET_VALUE_PLACEHOLDER,
            "ssh_password should return placeholder after deletion",
        )
        self.assertEqual(
            server.host_key,
            self.Server.SECRET_VALUE_PLACEHOLDER,
            "host_key should return placeholder after deletion",
        )

    def test_vault_mixin_bulk_create_with_secret_fields(self):
        """Test vault mixin functionality when creating multiple servers with different
        secret field configurations"""
        placeholder = self.Server.SECRET_VALUE_PLACEHOLDER
        # Create 3 servers with different secret field configurations
        servers_data = [
            {
                "name": "Server 1 - Both Fields",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password1",
                "ssh_auth_mode": "p",
                "os_id": self.os_debian_10.id,
                "host_key": "host_key1",
                "skip_host_key": False,
            },
            {
                "name": "Server 2 - Host Key Only",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_auth_mode": "k",
                "os_id": self.os_debian_10.id,
                "host_key": "host_key2",
                "skip_host_key": False,
                "ssh_key_id": self.key_1.id,
            },
            {
                "name": "Server 3 - SSH Password Only",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password3",
                "ssh_auth_mode": "p",
                "os_id": self.os_debian_10.id,
                "skip_host_key": True,
            },
        ]

        # Create all servers in one call
        servers = self.Server.create(servers_data)

        # Verify we have 3 servers
        self.assertEqual(len(servers), 3, "Should have created 3 servers")

        # Test 1: Get values for all 3 servers regular way - should return placeholders
        for server in servers:
            self.assertEqual(
                server.ssh_password,
                placeholder,
                f"Server {server.name} ssh_password should return placeholder "
                f"when read normally",
            )

            self.assertEqual(
                server.host_key,
                placeholder,
                f"Server {server.name} host_key should return placeholder "
                f"when read normally",
            )

        # Test 2: Get values for all 3 servers at once using _get_secret_values()
        all_secret_values = servers._get_secret_values()
        self.assertIsNotNone(all_secret_values, "all_secret_values should not be None")

        # Verify Server 1 (both fields)
        server1 = servers[0]
        self.assertIn(
            server1.id, all_secret_values, "Server 1 should be in secret values"
        )
        server1_secrets = all_secret_values[server1.id]

        self.assertEqual(
            server1_secrets.get("ssh_password"),
            "password1",
            "Server 1 ssh_password should be preserved correctly in vault",
        )
        self.assertEqual(
            server1_secrets.get("host_key"),
            "host_key1",
            "Server 1 host_key should be preserved correctly in vault",
        )

        # Verify Server 2 (host key only)
        server2 = servers[1]
        self.assertIn(
            server2.id, all_secret_values, "Server 2 should be in secret values"
        )
        server2_secrets = all_secret_values[server2.id]

        self.assertIsNone(
            server2_secrets.get("ssh_password"),
            "Server 2 should not have ssh_password in vault",
        )
        self.assertEqual(
            server2_secrets.get("host_key"),
            "host_key2",
            "Server 2 host_key should be preserved correctly in vault",
        )

        # Verify Server 3 (ssh password only)
        server3 = servers[2]
        self.assertIn(
            server3.id, all_secret_values, "Server 3 should be in secret values"
        )
        server3_secrets = all_secret_values[server3.id]

        self.assertEqual(
            server3_secrets.get("ssh_password"),
            "password3",
            "Server 3 ssh_password should be preserved correctly in vault",
        )
        self.assertIsNone(
            server3_secrets.get("host_key"),
            "Server 3 should not have host_key in vault",
        )

        # Test 3: Verify that non-secret fields are not affected
        for server in servers:
            self.assertIsNotNone(
                server.name,
                f"Server {server.id} name should not be affected by vault mixin",
            )
            self.assertIsNotNone(
                server.ssh_username,
                f"Server {server.id} ssh_username should not be affected "
                f"by vault mixin",
            )
            self.assertIsNotNone(
                server.ip_v4_address,
                f"Server {server.id} ip_v4_address should not be affected "
                f"by vault mixin",
            )

        # Test 4: Modify secret fields and verify changes are handled correctly
        # Change the ssh password and remove the host key from Server 1
        server1 = servers.filtered(lambda s: s.name == "Server 1 - Both Fields")
        server1.write(
            {
                "ssh_password": "updated_password1",
                "host_key": False,
            }
        )

        # Remove host key and add an ssh password in Server 2
        server2 = servers.filtered(lambda s: s.name == "Server 2 - Host Key Only")
        server2.write(
            {
                "host_key": False,
                "ssh_password": "new_password2",
            }
        )

        # Remove ssh password from Server 3
        server3 = servers.filtered(lambda s: s.name == "Server 3 - SSH Password Only")
        server3.write(
            {
                "ssh_password": False,
            }
        )

        # Test 5: Get values for all 3 servers regular way after modifications
        # Ensure that all values are replaced with placeholders
        for server in servers:
            self.assertEqual(
                server.ssh_password,
                placeholder,
                f"Server {server.id} ssh_password should return placeholder "
                f"after modifications",
            )
            self.assertEqual(
                server.host_key,
                placeholder,
                f"Server {server.id} host_key should return placeholder "
                f"after modifications",
            )

        # Test 6: Get values for all 3 servers at once using _get_secret_values()
        # Ensure that all values are preserved correctly after modifications
        all_secret_values = servers._get_secret_values()
        self.assertIsNotNone(
            all_secret_values,
            "all_secret_values should not be None after modifications",
        )

        # Verify Server 1 (updated password, no host key)
        server1 = servers[0]
        server1_secrets = all_secret_values[server1.id]

        self.assertEqual(
            server1_secrets.get("ssh_password"),
            "updated_password1",
            "Server 1 ssh_password should be updated correctly in vault",
        )
        self.assertIsNone(
            server1_secrets.get("host_key"),
            "Server 1 host_key should be removed from vault",
        )

        # Verify Server 2 (new password, no host key)
        server2_secrets = all_secret_values[server2.id]

        self.assertEqual(
            server2_secrets.get("ssh_password"),
            "new_password2",
            "Server 2 ssh_password should be added correctly in vault",
        )
        self.assertIsNone(
            server2_secrets.get("host_key"),
            "Server 2 host_key should be removed from vault",
        )

        # Verify Server 3 (no ssh password, no host key)
        # Server 3 should not be in the result since it has no secret values
        self.assertNotIn(
            server3.id,
            all_secret_values,
            "Server 3 should not be in secret values since it has no secret fields",
        )
