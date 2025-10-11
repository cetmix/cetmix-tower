from odoo.exceptions import AccessError, ValidationError

from ..models.constants import COMMAND_NOT_COMPATIBLE_WITH_SERVER
from .common import TestTowerCommon


class TestTowerServer(TestTowerCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.os_ubuntu_20_04 = cls.env["cx.tower.os"].create({"name": "Ubuntu 20.04"})

        # Define model variables to avoid unsubscriptable errors
        Key = cls.env["cx.tower.key"]
        Server = cls.env["cx.tower.server"]

        secret_1 = Key.create(
            {
                "name": "Secret 1",
                "secret_value": "secret_value_1",
                "key_type": "s",
            },
        )
        secret_2 = Key.create(
            {
                "name": "Secret 2",
                "secret_value": "secret_value_2",
                "key_type": "s",
            },
        )
        cls.server_test_2 = Server.create(
            {
                "name": "Test Server #2",
                "color": 2,
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "k",
                "host_key": "test_key",
                "use_sudo": "p",
                "ssh_key_id": cls.key_1.id,
                "os_id": cls.os_ubuntu_20_04.id,
                "secret_ids": [
                    (
                        0,
                        0,
                        {
                            "key_id": secret_1.id,
                            "secret_value": "secret_value_1",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "key_id": secret_2.id,
                            "secret_value": "secret_value_2",
                        },
                    ),
                ],
                "tag_ids": [(6, 0, [cls.tag_test_production.id])],
            }
        )

        # Files
        File = cls.env["cx.tower.file"]
        cls.server_test_2_file = File.create(
            {
                "name": "tower_demo_without_template_{{ branch }}.txt",
                "source": "tower",
                "server_id": cls.server_test_2.id,
                "server_dir": "{{ test_path }}",
                "code": "Please, check url: {{ url }}",
            }
        )

        # Flight plan to delete the server
        Command = cls.env["cx.tower.command"]
        Plan = cls.env["cx.tower.plan"]

        # Add a command to delete the server
        cls.command_delete_server = Command.create(
            {
                "name": "Python command for deleting server",
                "action": "python_code",
                "code": """
partner = env["res.partner"].create({"name": "Partner 1", "ref": "delete_server"})
result = {
    "exit_code": 0,
    "message": partner.name,
}
    """,
            }
        )

        cls.plan_delete_server = Plan.create(
            {
                "name": "Delete server",
                "line_ids": [
                    (0, 0, {"command_id": cls.command_delete_server.id, "sequence": 1}),
                ],
            }
        )

        # Create two test users that belong only to the "User" group.
        cls.user1 = cls.Users.create(
            {
                "name": "Test User 1",
                "login": "test_user1",
                "email": "test_user1@example.com",
                "groups_id": [(6, 0, [cls.group_user.id])],
            }
        )
        cls.user2 = cls.Users.create(
            {
                "name": "Test User 2",
                "login": "test_user2",
                "email": "test_user2@example.com",
                "groups_id": [(6, 0, [cls.group_user.id])],
            }
        )
        # Create two "Manager" group users.
        cls.manager1 = cls.Users.create(
            {
                "name": "Manager 1",
                "login": "manager1",
                "email": "manager1@example.com",
                "groups_id": [(6, 0, [cls.group_manager.id])],
            }
        )
        cls.manager2 = cls.Users.create(
            {
                "name": "Manager 2",
                "login": "manager2",
                "email": "manager2@example.com",
                "groups_id": [(6, 0, [cls.group_manager.id])],
            }
        )

    def test_server_copy(self):
        """Test server copy"""

        # Let's say we have auto sync enabled on one of the files in server 2
        self.server_test_2_file.auto_sync = True
        fields_to_check = [
            "ip_v4_address",
            "ip_v6_address",
            "ssh_username",
            "ssh_password",
            "ssh_key_id",
        ]

        # Crete a log from file of type 'server'
        file_for_log = self.File.create(
            {
                "source": "server",
                "name": "test.log",
                "server_dir": "/tmp",
                "server_id": self.server_test_2.id,
                "code": "Some log record - server",
            }
        )

        server_log_server = self.ServerLog.create(
            {
                "name": "Log from file",
                "server_id": self.server_test_2.id,
                "log_type": "file",
                "file_id": file_for_log.id,
            }
        )
        # Add variable values to server
        self.env["cx.tower.variable.value"].create(
            {
                "server_id": self.server_test_2.id,
                "variable_id": self.variable_dir.id,
                "value_char": "test",
            }
        )

        # Copy server 2
        server_test_2_copy = self.server_test_2.copy()

        # The name of copy should contain '~ (copy)' suffix
        self.assertTrue(
            server_test_2_copy.name == self.server_test_2.name + " (copy)",
            msg="Server name should contain '~ (copy)' suffix!",
        )

        # Check server logs
        # Check that the copied server has the same number of server logs
        self.assertEqual(
            len(server_test_2_copy.server_log_ids),
            len(self.server_test_2.server_log_ids),
            (
                "Copied template should have the same "
                "number of server logs as the original"
            ),
        )

        # Ensure the first server log in the copied server matches the original
        copied_log = server_test_2_copy.server_log_ids
        self.assertEqual(
            copied_log.name,
            server_log_server.name,
            "Server log name should be the same in the copied server",
        )
        self.assertEqual(
            copied_log.command_id.id,
            server_log_server.command_id.id,
            "Command ID should be the same in the copied server log",
        )
        self.assertEqual(
            copied_log.command_id.code,
            server_log_server.command_id.code,
            "Command code should be the same in the copied server log",
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
                    for key_src, key_copy in zip(  # noqa: B905 we need to run on Python 3.10
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
                    var_copy.variable_reference == var_src.variable_reference
                    and var_copy.value_char == var_src.value_char
                    for var_src, var_copy in zip(  # noqa: B905 we need to run on Python 3.10
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

        # Copy copied server
        server_test_2_new_copy = server_test_2_copy.copy()
        # Variable names and values in server copy should be the same
        # as in source server
        self.assertTrue(
            all(
                [
                    var_copy.variable_reference == var_src.variable_reference
                    and var_copy.value_char == var_src.value_char
                    and var_copy.reference == f"{var_src.reference}_copy"
                    for var_src, var_copy in zip(  # noqa: B905 we need to run on Python 3.10
                        server_test_2_copy.variable_value_ids,
                        server_test_2_new_copy.variable_value_ids,
                    )
                ]
            ),
            msg=(
                "Variable names and values in server copy "
                "should be the same as in source server!"
            ),
        )

    def test_server_archive_unarchive(self):
        """Test Server archived/unarchived"""
        server = self.server_test_1.copy()
        self.assertTrue(server, msg="Server must be unarchived")
        server.toggle_active()
        server.toggle_active()
        self.assertTrue(server, msg="Server must be unarchived")

    def test_server_unlink(self):
        """
        Test cascading deletion of server and its related records.
        """
        secret_1 = self.Key.create(
            {
                "name": "Secret 1",
                "secret_value": "secret_value_1",
                "key_type": "s",
            },
        )
        # Create a test server
        server = self.Server.create(
            {
                "name": "Test Server #3",
                "color": 3,
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "k",
                "use_sudo": "p",
                "ssh_key_id": self.key_1.id,
                "host_key": "test_key",
                "os_id": self.os_ubuntu_20_04.id,
                "secret_ids": [
                    (
                        0,
                        0,
                        {
                            "key_id": secret_1.id,
                            "secret_value": "secret_value_1",
                        },
                    ),
                ],
            }
        )

        # Create related file
        file = self.File.create(
            {"name": "Test File", "server_id": server.id, "source": "server"}
        )

        # Related secret
        secret = server.secret_ids[0]

        variable_meme = self.Variable.create({"name": "meme"})

        # Create related variable value
        variable_value = self.env["cx.tower.variable.value"].create(
            {
                "variable_id": variable_meme.id,  # Replace with valid reference
                "value_char": "Test Value",
                "server_id": server.id,
            }
        )
        plan_1 = self.Plan.create(
            {
                "name": "Test plan",
                "note": "Create directory and list its content",
            }
        )
        # Create a related plan log
        plan_log = self.PlanLog.create(
            {
                "server_id": server.id,
                "plan_id": plan_1.id,  # Replace with valid reference
            }
        )

        # Check that all records are created
        self.assertTrue(server, "Server should be created successfully")
        self.assertTrue(file, "File should be created successfully")
        self.assertTrue(secret, "Secret should be created successfully")
        self.assertTrue(variable_value, "Variable Value should be created successfully")
        self.assertTrue(plan_log, "Plan Log should be created successfully")

        # Collect IDs for verification post-deletion
        file_id = file.id
        variable_value_id = variable_value.id
        plan_log_id = plan_log.id

        # Delete the server
        server.unlink()

        # Verify that the server is deleted
        self.assertFalse(
            self.Server.search([("id", "=", server.id)]),
            msg="Server should be deleted",
        )
        # Verify that related records are deleted
        self.assertFalse(
            self.File.search([("id", "=", file_id)]),
            msg="File should be deleted when server is deleted",
        )
        # Verify that unrelated records are not affected
        self.assertTrue(
            self.Plan.search([("id", "=", plan_1.id)]),
            msg="Unrelated plan should not be deleted when server is deleted",
        )
        self.assertFalse(
            self.KeyValue.search([("id", "=", secret.id)]),
            msg="Secret should be deleted when server is deleted",
        )
        self.assertFalse(
            self.VariableValue.search([("id", "=", variable_value_id)]),
            msg="Variable Value should be deleted when server is deleted",
        )
        self.assertFalse(
            self.PlanLog.search([("id", "=", plan_log_id)]),
            msg="Plan Log should be deleted when server is deleted",
        )

    def test_server_delete_plan_success(self):
        """Test server delete plan"""

        # Set plan to delete the server
        self.server_test_2.plan_delete_id = self.plan_delete_server.id

        # Delete the server
        self.server_test_2.unlink()

        # Check if the server has been deleted
        self.assertFalse(
            self.server_test_2.exists(),
            msg="Server should be deleted",
        )

        # Check if the partner has been created
        self.assertTrue(
            self.env["res.partner"].search([("ref", "=", "delete_server")]),
            msg="Partner should be created",
        )

    def test_server_delete_plan_error(self):
        """Test server delete plan error"""

        # Modify the command to fail
        self.command_delete_server.code = """
result = {
    "exit_code": 4,
    "message": 'Such much error',
}
    """
        # Set plan to delete the server
        self.server_test_2.plan_delete_id = self.plan_delete_server.id

        # Delete the server
        self.server_test_2.unlink()

        # Check if the server has been deleted
        self.assertTrue(
            self.server_test_2.exists(),
            msg="Server should not be deleted",
        )

        self.assertEqual(
            self.server_test_2.status,
            "delete_error",
            msg="Server status should be delete_error",
        )

    # ------------------------------------------------------------
    # ---- Access
    # ------------------------------------------------------------
    def test_user_record_not_visible_without_user_ids(self):
        """
        Test that a user in the 'cetmix_tower_server.group_user' group cannot see
        a Tower Server record if not added to user_ids.
        """
        # Create a Tower Server record without any user_ids.
        record = self.Server.create(
            {
                "name": "User Visibility Test",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "os_id": self.os_debian_10.id,
                "user_ids": [(5, 0, 0)],
            }
        )
        # As user1, search for the record. Since user1's partner is not subscribed,
        # the record should not be returned.
        records = self.Server.with_user(self.user1).search([("id", "=", record.id)])
        self.assertFalse(
            records,
            "User1 should not see the record if not added to user_ids.",
        )

    def test_user_record_visible_after_added_to_user_ids(self):
        """
        Test that a user sees a Tower Server record after being added to user_ids.
        """
        record = self.Server.create(
            {
                "name": "User Visibility Test",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "os_id": self.os_debian_10.id,
                "user_ids": [(4, self.user1.id)],
            }
        )
        # Now, as user1 the record should be visible.
        records = self.Server.with_user(self.user1).search([("id", "=", record.id)])
        self.assertTrue(
            records,
            "User1 should see the record after being added to message_partner_ids.",
        )

    def test_only_added_user_can_see(self):
        """
        Test that only the added user can see the Tower Server record.
        """
        record = self.Server.create(
            {
                "name": "User Visibility Test",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "os_id": self.os_debian_10.id,
                "user_ids": [(4, self.user1.id)],
            }
        )
        # Subscribe only user1's partner.
        records_user1 = self.Server.with_user(self.user1).search(
            [("id", "=", record.id)]
        )
        records_user2 = self.Server.with_user(self.user2).search(
            [("id", "=", record.id)]
        )
        self.assertTrue(
            records_user1, "User1 should see the record after being added to user_ids."
        )
        self.assertFalse(
            records_user2,
            "User2 should not see the record if they are not added to user_ids.",
        )

    def test_manager_read_access_as_follower(self):
        """A manager should be able to read a record if his partner is a follower."""

        # Create a record without any managers in manager_ids.
        record = self.Server.create(
            {
                "name": "Test Server (Follower)",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "os_id": self.os_debian_10.id,
                # Explicitly clear manager_ids
                "manager_ids": [(6, 0, [])],
            }
        )
        # Subscribe manager1 to the record so that his partner becomes a follower.
        record.write({"user_ids": [(4, self.manager1.id)]})

        # As manager1 (a follower) the record should be visible.
        records = self.Server.with_user(self.manager1).search([("id", "=", record.id)])
        self.assertTrue(records, "Manager1 (user) must be able to read the record.")

        # As manager2 (not a follower and not in manager_ids)
        # the record should not be visible.
        records = self.Server.with_user(self.manager2).search([("id", "=", record.id)])
        self.assertFalse(
            records,
            "Manager2 (not user_ids and not in manager_ids) must not see the record.",
        )

    def test_manager_read_access_as_manager_ids(self):
        """A manager should be able to read a record if he is added to manager_ids."""

        # Create a record with manager2 added to manager_ids.
        record = self.Server.create(
            {
                "name": "Test Server (Manager)",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "os_id": self.os_debian_10.id,
                "manager_ids": [(6, 0, [self.manager2.id])],
            }
        )
        # Without adding to user_ids, manager2 should be able to see the record.
        records = self.Server.with_user(self.manager2).search([("id", "=", record.id)])
        self.assertTrue(
            records, "Manager2 (in manager_ids) must be able to read the record."
        )

        # Manager1 is not added to user_ids nor in manager_ids
        # so should not see the record.
        records = self.Server.with_user(self.manager1).search([("id", "=", record.id)])
        self.assertFalse(
            records,
            "Manager1 (neither user_ids nor in manager_ids) must not see the record.",
        )

        # Add manager1 to user_ids
        record.write({"user_ids": [(4, self.manager1.id)]})
        records = self.Server.with_user(self.manager1).search([("id", "=", record.id)])
        self.assertTrue(
            records,
            "Manager1 (added to user_ids) must be able to see the record.",
        )

    def test_manager_write_access(self):
        """A manager should be able to update a record only if he is in manager_ids."""

        # Create a record with no managers.
        record = self.Server.create(
            {
                "name": "Test Server (Write)",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "os_id": self.os_debian_10.id,
                "manager_ids": [(6, 0, [])],
            }
        )

        # Manager1 (not in manager_ids) tries to update: should raise an AccessError.
        with self.assertRaises(AccessError):
            record.with_user(self.manager1).write({"name": "Updated Name"})

        # Update the record to include manager1 in manager_ids.
        record.write({"manager_ids": [(4, self.manager1.id)]})
        try:
            record.with_user(self.manager1).write({"name": "Updated Name"})
        except AccessError:
            self.fail(
                "Manager1 must be able to update the "
                "record after being added to manager_ids."
            )

    def test_manager_create_access(self):
        """
        A manager should be allowed to create a record only if he is added
        in the "Managers".
        """
        # Manager1 attempts to create a record without including himself in manager_ids.
        with self.assertRaises(AccessError):
            self.Server.with_user(self.manager1).create(
                {
                    "name": "Test Server (Create Denied)",
                    "ip_v4_address": "localhost",
                    "ssh_username": "admin",
                    "ssh_password": "password",
                    "ssh_auth_mode": "p",
                    "os_id": self.os_debian_10.id,
                    "manager_ids": [(6, 0, [])],
                }
            )

        # Manager1 creates a record with himself added to manager_ids.
        try:
            record = self.Server.with_user(self.manager1).create(
                {
                    "name": "Test Server (Create Allowed)",
                    "ip_v4_address": "localhost",
                    "ssh_username": "admin",
                    "ssh_password": "password",
                    "ssh_auth_mode": "p",
                    "os_id": self.os_debian_10.id,
                    "manager_ids": [(6, 0, [self.manager1.id])],
                }
            )
            self.assertTrue(
                record,
                "Manager1 must be able to create the record if he is in manager_ids.",
            )
        except AccessError:
            self.fail(
                "Manager1 should be allowed to create a "
                "record when included in manager_ids."
            )

    def test_manager_delete_access(self):
        """
        A manager should be allowed to delete a record only if:
         - He is in the manager_ids field, and
         - He is the creator of the record.
        """

        # -- Scenario 1: Manager1 creates a record with himself in manager_ids.
        record = self.Server.with_user(self.manager1).create(
            {
                "name": "Test Server (Delete Allowed)",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "os_id": self.os_debian_10.id,
                "manager_ids": [(6, 0, [self.manager1.id])],
            }
        )
        # Manager1 should be able to delete his own record.
        try:
            record.with_user(self.manager1).unlink()
        except AccessError:
            self.fail(
                "Manager1 must be able to delete his own record if in manager_ids."
            )

        # -- Scenario 2: Manager2 creates a record (with himself in manager_ids).
        record2 = self.Server.with_user(self.manager2).create(
            {
                "name": "Test Server (Delete Denied - Not Creator)",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "os_id": self.os_debian_10.id,
                "manager_ids": [(6, 0, [self.manager2.id, self.manager1.id])],
            }
        )
        # Manager1, should not be able to delete record2.
        with self.assertRaises(AccessError):
            record2.with_user(self.manager1).unlink()

        # Remove manager2 from manager_ids.
        record2.write({"manager_ids": [(6, 0, [])]})

        # Manager2 should not be able to delete record2 now
        # because he is not in manager_ids.
        with self.assertRaises(AccessError):
            record2.with_user(self.manager2).unlink()

    def test_command_server_compatibility(self):
        """Test command compatibility with servers"""
        # Create a command restricted to specific servers
        command = self.Command.create(
            {
                "name": "Restricted Command",
                "action": "ssh_command",
                "code": "echo 'test'",
                "server_ids": [(6, 0, [self.server_test_1.id])],
            }
        )

        # Should work on allowed server
        try:
            self.server_test_1.run_command(command)
        except Exception as e:
            self.fail(f"Command should execute on allowed server but failed: {e}")

        # Should fail on non-allowed server
        command_result = self.server_test_2.with_context(
            no_command_log=True
        ).run_command(command)
        self.assertEqual(
            command_result["status"],
            COMMAND_NOT_COMPATIBLE_WITH_SERVER,
            "Command should not execute on non-allowed server",
        )

        # Clear all existing command logs
        self.CommandLog.search([]).unlink()
        # Same test but with command log
        self.server_test_2.run_command(command)

        command_log = self.CommandLog.search([])
        self.assertEqual(len(command_log), 1, "Must be a single log record")
        self.assertEqual(
            command_log.command_status,
            COMMAND_NOT_COMPATIBLE_WITH_SERVER,
            "Command should not execute on non-allowed server",
        )

        # Command without server restrictions should work on any server
        unrestricted_command = self.Command.create(
            {
                "name": "Unrestricted Command",
                "action": "ssh_command",
                "code": "echo 'test'",
            }
        )

        try:
            self.server_test_1.run_command(unrestricted_command)
            self.server_test_2.run_command(unrestricted_command)
        except Exception as e:
            self.fail(
                f"Unrestricted command should execute on any server but failed: {e}"
            )

    def test_server_host_key_validation(self):
        """Test server host key validation"""
        server = self.Server.create(
            {
                "name": "Test Server",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "os_id": self.os_debian_10.id,
                "host_key": "test_key",
                "skip_host_key": False,
            }
        )
        # Test with host key
        server.test_ssh_connection()

        # Test without host key
        server.host_key = None
        with self.assertRaises(ValidationError):
            server.test_ssh_connection()

        # Test with skip_host_key
        server.skip_host_key = True
        server.test_ssh_connection()

    def test_server_reference_update(self):
        """Test server reference update cascades to dependent models"""
        # 1. Add a variable value to server_test_1
        variable_value = self.VariableValue.create(
            {
                "variable_id": self.variable_os.id,
                "value_char": "Ubuntu 20.04",
                "server_id": self.server_test_1.id,
            }
        )

        # 2. Add a file to server_test_1
        server_file = self.File.create(
            {
                "name": "test_file.txt",
                "server_id": self.server_test_1.id,
                "source": "tower",
                "code": "Test file content",
            }
        )

        # Store original references for comparison
        original_server_reference = self.server_test_1.reference
        original_variable_value_reference = variable_value.reference
        original_file_reference = server_file.reference

        # 3. Change the reference for server_test_1 to "awesome_server"
        self.server_test_1.write({"reference": "awesome_server"})

        # 4. Verify that references are updated for dependent models
        # Invalidate models to refresh all references
        self.env["cx.tower.server"].invalidate_model(["reference"])
        self.env["cx.tower.variable.value"].invalidate_model(["reference"])
        self.env["cx.tower.file"].invalidate_model(["reference"])

        # Check that server reference was updated
        self.assertEqual(self.server_test_1.reference, "awesome_server")
        self.assertNotEqual(self.server_test_1.reference, original_server_reference)

        # Check that variable value reference was updated
        # to include the new server reference
        self.assertIn("awesome_server", variable_value.reference)
        self.assertNotEqual(variable_value.reference, original_variable_value_reference)

        # Check that file reference was updated to include the new server reference
        self.assertIn("awesome_server", server_file.reference)
        self.assertNotEqual(server_file.reference, original_file_reference)

        # Verify the reference pattern for variable value follows the expected format:
        # <variable_reference>_<model_generic_reference>_<linked_model_generic_reference>_<linked_record_reference>  # noqa: E501
        expected_variable_pattern = (
            f"{self.variable_os.reference}_variable_value_server_"
            f"{self.server_test_1.reference}"
        )
        self.assertEqual(variable_value.reference, expected_variable_pattern)

        # Verify the reference pattern for file follows the expected format:
        # <parent_reference>_<model_generic_reference>_<index>
        expected_file_pattern = f"{self.server_test_1.reference}_file_1"
        self.assertEqual(server_file.reference, expected_file_pattern)
