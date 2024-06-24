from odoo.exceptions import AccessError

from .common import TestTowerCommon


class TestTowerServer(TestTowerCommon):
    def setUp(self, *args, **kwargs):
        super().setUp(*args, **kwargs)
        self.os_ubuntu_20_04 = self.env["cx.tower.os"].create({"name": "Ubuntu 20.04"})
        self.server_test_2 = self.Server.create(
            {
                "name": "Test Server #2",
                "color": 2,
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "k",
                "use_sudo": "p",
                "ssh_key_id": self.key_1.id,
                "os_id": self.os_ubuntu_20_04.id,
                "secret_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Secret 1",
                            "secret_value": "secret_value_1",
                            "key_type": "s",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "Secret 2",
                            "secret_value": "secret_value_2",
                            "key_type": "s",
                        },
                    ),
                ],
                "tag_ids": [
                    (6, 0, [self.env.ref("cetmix_tower_server.tag_production").id])
                ],
            }
        )
        # Files
        self.File = self.env["cx.tower.file"]
        self.server_test_2_file = self.File.create(
            {
                "name": "tower_demo_without_template_{{ branch }}.txt",
                "source": "tower",
                "server_id": self.server_test_2.id,
                "server_dir": "{{ test_path }}",
                "code": "Please, check url: {{ url }}",
            }
        )

    def test_server_copy(self):
        # Let's say we have auto sync enabled on one of the files in server 2
        self.server_test_2_file.auto_sync = True
        fields_to_check = [
            "ip_v4_address",
            "ip_v6_address",
            "ssh_username",
            "ssh_password",
            "ssh_key_id",
        ]

        # Copy server 2
        server_test_2_copy = self.server_test_2.copy()

        # The name of copy should contain '~ (copy)' suffix
        self.assertTrue(
            server_test_2_copy.name == self.server_test_2.name + " (copy)",
            msg="Server name should contain '~ (copy)' suffix!",
        )

        # Check fields match list
        for field_ in fields_to_check:
            self.assertTrue(
                getattr(server_test_2_copy, field_)
                == getattr(self.server_test_2, field_),
                msg=(
                    f"Field {field_} value on server copy "
                    "does not match with the source!"
                ),
            )

        # Check if auto sync is disabled on the all the files
        # in the copied server
        self.assertTrue(
            all([not file.auto_sync for file in server_test_2_copy.file_ids]),
            msg="Auto sync should be disabled on all the files in the copied server!",
        )

        # Check if 'keep_when_deleted' option is enabled on all the files
        # in the copied server
        self.assertTrue(
            all([file.keep_when_deleted for file in server_test_2_copy.file_ids]),
            msg=(
                "keep_when_deleted option should be enabled on all the files "
                "in the copied server!"
            ),
        )

        # Check if secret values of keys in the copied server are the same
        # as in source server
        self.assertTrue(
            all(
                [
                    key_copy.secret_value == key_src.secret_value
                    for key_src, key_copy in zip(
                        self.server_test_2.secret_ids.sudo(),
                        server_test_2_copy.secret_ids.sudo(),
                    )
                ]
            ),
            msg=(
                "Secret values of keys in the copied server "
                "should be the same as in source server!"
            ),
        )

        # Variable names and values in server copy should be the same
        # as in source server
        self.assertTrue(
            all(
                [
                    var_copy.variable_name == var_src.variable_name
                    and var_copy.value_char == var_src.value_char
                    for var_src, var_copy in zip(
                        self.server_test_2.variable_value_ids,
                        server_test_2_copy.variable_value_ids,
                    )
                ]
            ),
            msg=(
                "Variable names and values in server copy "
                "should be the same as in source server!"
            ),
        )

    def test_server_access_rights(self):
        """Test Server access rights"""

        # Bob is a regular user with no access to Servers
        server_1_as_bob = self.server_test_1.with_user(self.user_bob)

        # Invalidating cache so values will be fetched again with access check applied
        server_1_as_bob.invalidate_cache()

        # Access error should be raised because user has no access to the model
        with self.assertRaises(AccessError):
            server_name = server_1_as_bob.name

        # Add Bob to group_user and test read as unsubscribed user
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")
        with self.assertRaises(AccessError):
            server_name = server_1_as_bob.name

        # Add Bob to group_manager and test read as unsubscribed user
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        with self.assertRaises(AccessError):
            server_name = server_1_as_bob.name

        # Add Bob to group_root and test read
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_root")
        server_name = server_1_as_bob.name
        self.assertEqual(
            server_name, self.server_test_1.name, msg="Sever name does not match!"
        )

        # Test write as root
        self.write_and_invalidate(server_1_as_bob, **{"name": "New Server Name"})

    def test_server_subscriber_access_rights(self):
        """Test Server access rights"""
        # Create additional server for testing
        new_server = self.Server.create(
            {
                "name": "Test 2",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "os_id": self.os_debian_10.id,
            }
        )

        server_1_as_bob = self.server_test_1.with_user(self.user_bob)
        server_2_as_bob = new_server.with_user(self.user_bob)

        # Invalidating cache so values will be fetched again with access check applied
        server_1_as_bob.invalidate_cache()
        server_2_as_bob.invalidate_cache()

        # Add Bob to group_user and test read as subscribed user
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_user")
        # Add Bob to followers of that server
        self.server_test_1.message_subscribe([self.user_bob.partner_id.id])

        # Access error should be raised because user hasn't subscribed to server 2
        with self.assertRaises(AccessError):
            server_name = server_2_as_bob.name

        # Check if user Bob can read server 1 name as subscribed user
        server_name = server_1_as_bob.name
        self.assertEqual(
            server_name, self.server_test_1.name, msg="Sever name does not match!"
        )

        # Add Bob to group_manager and test write
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        self.write_and_invalidate(server_1_as_bob, **{"name": "New Server Name"})
        self.assertEqual(
            self.server_test_1.name, "New Server Name", msg="Sever name does not match!"
        )

        # Access error should be raised because user Bob hasn't subscribed to server 2
        with self.assertRaises(AccessError):
            server_name = server_2_as_bob.name

        # Check if user Bob can create new server as member of group_manager
        new_server_1 = self.Server.with_user(self.user_bob).create(
            {
                "name": "Test Server 2",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "os_id": self.os_debian_10.id,
            }
        )
        # Check if server has been created by Bob as member of group_manager
        self.assertEqual(
            new_server_1.name, "Test Server 2", msg="Sever name does not match!"
        )

        # Check if user Bob can unlink new server as member of group_manager
        with self.assertRaises(
            AccessError,
            msg="member of group_manager should \
                                not be able to unlink servers",
        ):
            new_server_1.with_user(self.user_bob).unlink()
        # Read as sudo and check if the value is updated

    def test_server_archived_unarchived(self):
        """Test Server archived/unarchived"""
        server = self.server_test_1.copy()
        self.assertTrue(server, msg="Server must be unarchived")
        server.toggle_active()
        server.toggle_active()
        self.assertTrue(server, msg="Server must be unarchived")
