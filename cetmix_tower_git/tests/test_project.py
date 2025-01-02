from odoo.exceptions import AccessError

from .common import CommonTest


class TestFileRel(CommonTest):
    """Test class for git file relation."""

    def setUp(self):
        super().setUp()
        # Remove user bob from all groups
        self.remove_from_group(
            self.user_bob,
            [
                "cetmix_tower_server.group_user",
                "cetmix_tower_server.group_manager",
                "cetmix_tower_server.group_root",
            ],
        )

        # Unsubscribe user bob from server 1
        self.server_test_1.message_unsubscribe([self.user_bob.partner_id.id])

        # Entities as Bob
        self.project_as_bob = self.git_project_1.with_user(self.user_bob)
        self.source_as_bob = self.git_source_1.with_user(self.user_bob)
        self.remote_as_bob = self.remote_other_ssh.with_user(self.user_bob)

    def test_project_access(self):
        """Test access rules for git projects"""

        # -- 1 --
        # Check if Bob can read project, source and remote
        with self.assertRaises(AccessError):
            self.project_as_bob.read([])
        with self.assertRaises(AccessError):
            self.source_as_bob.read([])
        with self.assertRaises(AccessError):
            self.remote_as_bob.read([])

        # -- 2 --
        # Add Bod to the Manager group
        # Bob should be able to read the project, source and remote
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        res = self.project_as_bob.read([])
        self.assertEqual(
            res[0]["name"],
            self.git_project_1.name,
            "Bob should be able to read project",
        )
        res = self.source_as_bob.read([])
        self.assertEqual(
            res[0]["name"], self.git_source_1.name, "Bob should be able to read source"
        )
        res = self.remote_as_bob.read([])
        self.assertEqual(
            res[0]["name"],
            self.remote_other_ssh.name,
            "Bob should be able to read remote",
        )

        # -- 3 --
        # Link server to project
        # Bob should not be able read the project, source and remote
        # because he is not subscribed to the server
        self.GitProjectRel.create(
            {
                "server_id": self.server_test_1.id,
                "file_id": self.server_1_file_1.id,
                "git_project_id": self.git_project_1.id,
                "project_format": "git_aggregator",
            }
        )
        with self.assertRaises(AccessError):
            self.project_as_bob.read([])
        with self.assertRaises(AccessError):
            self.source_as_bob.read([])
        with self.assertRaises(AccessError):
            self.remote_as_bob.read([])

        # -- 4 --
        # Subscribe Bob to the server
        # Bob should be able to read the project, source and remote
        self.server_test_1.message_subscribe([self.user_bob.partner_id.id])
        res = self.project_as_bob.read([])
        self.assertEqual(
            res[0]["name"],
            self.git_project_1.name,
            "Bob should be able to read project",
        )
        res = self.source_as_bob.read([])
        self.assertEqual(
            res[0]["name"], self.git_source_1.name, "Bob should be able to read source"
        )
        res = self.remote_as_bob.read([])
        self.assertEqual(
            res[0]["name"],
            self.remote_other_ssh.name,
            "Bob should be able to read remote",
        )
