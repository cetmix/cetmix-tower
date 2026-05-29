from odoo.exceptions import AccessError

from .common import CommonTest


class TestSource(CommonTest):
    """Test class for git source."""

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

        # Create test project and source as root
        cls.project = cls.GitProject.create(
            {
                "name": "Test Project",
            }
        )
        cls.source = cls.GitSource.create(
            {
                "name": "Test Source",
                "git_project_id": cls.project.id,
            }
        )

    def test_user_access(self):
        """Test that regular users have no access to git sources"""
        user_source = self.GitSource.with_user(self.user)

        # Test CRUD operations
        with self.assertRaises(AccessError):
            user_source.create(
                {
                    "name": "New Source",
                    "git_project_id": self.project.id,
                }
            )
        with self.assertRaises(AccessError):
            user_source.browse(self.source.id).read(["name"])
        with self.assertRaises(AccessError):
            user_source.browse(self.source.id).write({"name": "Updated Name"})
        with self.assertRaises(AccessError):
            user_source.browse(self.source.id).unlink()

    def test_manager_read_access(self):
        """Test manager read access rules"""
        manager_source = self.GitSource.with_user(self.manager)

        # Manager not in project user_ids or manager_ids - should not read
        with self.assertRaises(AccessError):
            manager_source.browse(self.source.id).read(["name"])

        # Add manager to project user_ids - should read
        self.project.write({"user_ids": [(4, self.manager.id)]})
        self.assertEqual(manager_source.browse(self.source.id).name, "Test Source")

        # Remove from user_ids, add to manager_ids - should read
        self.project.write(
            {"user_ids": [(3, self.manager.id)], "manager_ids": [(4, self.manager.id)]}
        )
        self.assertEqual(manager_source.browse(self.source.id).name, "Test Source")

    def test_manager_write_access(self):
        """Test manager write/create access rules"""
        manager_source = self.GitSource.with_user(self.manager)

        # Create project as manager - should be added to manager_ids automatically
        project = self.GitProject.with_user(self.manager).create(
            {
                "name": "Manager Project",
            }
        )
        self.assertIn(self.manager, project.manager_ids)

        # Create source in own project - should succeed
        new_source = manager_source.create(
            {
                "name": "New Source",
                "git_project_id": project.id,
            }
        )
        self.assertTrue(new_source.exists())

        # Write to own source - should succeed
        new_source.write({"name": "Updated Name"})
        self.assertEqual(new_source.name, "Updated Name")

        # Write to other's source - should fail
        with self.assertRaises(AccessError):
            manager_source.browse(self.source.id).write({"name": "Updated Name"})

    def test_manager_unlink_access(self):
        """Test manager unlink access rules"""
        # Create project and source as manager_2
        project = self.GitProject.with_user(self.manager_2).create(
            {
                "name": "Manager 2 Project",
            }
        )
        source = self.GitSource.with_user(self.manager_2).create(
            {
                "name": "Source to Delete",
                "git_project_id": project.id,
            }
        )
        manager_source = self.GitSource.with_user(self.manager)

        # Try delete as different manager - should fail even if added to manager_ids
        project.write({"manager_ids": [(4, self.manager.id)]})
        with self.assertRaises(AccessError):
            manager_source.browse(source.id).unlink()

        # Create source as manager and try delete - should succeed
        own_source = manager_source.create(
            {
                "name": "Own Source",
                "git_project_id": project.id,
            }
        )
        self.assertTrue(own_source.exists())
        own_source.unlink()
        self.assertFalse(own_source.exists())

    def test_root_access(self):
        """Test root access rules"""
        root_source = self.GitSource.with_user(self.root)

        # Create
        new_source = root_source.create(
            {
                "name": "Root Source",
                "git_project_id": self.project.id,
            }
        )
        self.assertTrue(new_source.exists())

        # Read
        self.assertEqual(root_source.browse(self.source.id).name, "Test Source")

        # Write
        root_source.browse(self.source.id).write({"name": "Updated by Root"})
        self.assertEqual(self.source.name, "Updated by Root")

        # Delete
        new_source.unlink()
        self.assertFalse(new_source.exists())

    def test_source_git_aggregator_prepare_record(self):
        """Test if source prepare record method works correctly."""

        # -- 1 --
        # Source 1
        expected_result = {
            "remotes": {
                "remote_1": "https://github.com/cetmix-test/cetmix-tower-test.git",
                "remote_2": "https://$GITLAB_TOKEN_NAME:$GITLAB_TOKEN@my.gitlab.com/cetmix-test/cetmix-tower-test.git",
                "remote_3": "git@my.gitlab.com:cetmix-test/cetmix-tower-test.git",
            },
            "merges": [
                {"remote": "remote_1", "ref": "refs/pull/123/head"},
                {"remote": "remote_2", "ref": "main"},
                {"remote": "remote_3", "ref": "10000000"},
            ],
            "target": "remote_1",
        }
        prepared_result = self.git_source_1._git_aggregator_prepare_record()
        self.assertEqual(
            prepared_result, expected_result, "Prepared result is not correct"
        )

    def test_manager_server_based_access(self):
        """Test manager access to sources through server relationships"""
        manager_source = self.GitSource.with_user(self.manager)

        # Create a server where manager is a user
        server = self.Server.create(
            {
                "name": "Test Server",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "os_id": self.os_debian_10.id,
                "user_ids": [(4, self.manager.id)],
            }
        )

        # Link project to server
        file = self.File.create(
            {
                "name": "test_file",
                "server_id": server.id,
            }
        )
        self.GitProjectRel.create(
            {
                "server_id": server.id,
                "file_id": file.id,
                "git_project_id": self.project.id,
                "project_format": "git_aggregator",
            }
        )

        # Manager should be able to read source through server relationship
        self.assertEqual(manager_source.browse(self.source.id).name, "Test Source")

        # Remove manager from server users
        server.write({"user_ids": [(3, self.manager.id)]})

        # Manager should not be able to read source anymore
        with self.assertRaises(AccessError):
            manager_source.browse(self.source.id).read(["name"])

        # Add manager to server managers
        server.write({"manager_ids": [(4, self.manager.id)]})

        # Manager should be able to read source again
        self.assertEqual(manager_source.browse(self.source.id).name, "Test Source")
