from odoo.exceptions import AccessError

from .common import CommonTest


class TestProject(CommonTest):
    """Test class for git project."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Remove user bob from all groups
        cls.remove_from_group(
            cls.user_bob,
            [
                "cetmix_tower_server.group_user",
                "cetmix_tower_server.group_manager",
                "cetmix_tower_server.group_root",
            ],
        )

        # Create another manager for testing
        cls.manager_2 = cls.Users.create(
            {
                "name": "Second Manager",
                "login": "manager2",
                "email": "manager2@test.com",
                "groups_id": [(4, cls.env.ref("cetmix_tower_server.group_manager").id)],
            }
        )

        # Create test project as root
        cls.project = cls.GitProject.create(
            {
                "name": "Test Project",
            }
        )

    def test_user_access(self):
        """Test that regular users have no access to git projects"""
        user_project = self.GitProject.with_user(self.user)

        # Test CRUD operations
        with self.assertRaises(AccessError):
            user_project.create({"name": "New Project"})
        with self.assertRaises(AccessError):
            user_project.browse(self.project.id).read(["name"])
        with self.assertRaises(AccessError):
            user_project.browse(self.project.id).write({"name": "Updated Name"})
        with self.assertRaises(AccessError):
            user_project.browse(self.project.id).unlink()

    def test_manager_read_access(self):
        """Test manager read access rules"""
        manager_project = self.GitProject.with_user(self.manager)

        # Manager not in user_ids or manager_ids - should not read
        with self.assertRaises(AccessError):
            manager_project.browse(self.project.id).read(["name"])

        # Add manager to user_ids - should read
        self.project.write({"user_ids": [(4, self.manager.id)]})
        self.assertEqual(manager_project.browse(self.project.id).name, "Test Project")

        # Remove from user_ids, add to manager_ids - should read
        self.project.write(
            {"user_ids": [(3, self.manager.id)], "manager_ids": [(4, self.manager.id)]}
        )
        self.assertEqual(manager_project.browse(self.project.id).name, "Test Project")

    def test_manager_write_access(self):
        """Test manager write/create access rules"""
        manager_project = self.GitProject.with_user(self.manager)

        # Create - should succeed as manager is added by default
        new_project = manager_project.create({"name": "New Project"})
        self.assertTrue(new_project.exists())
        self.assertIn(self.manager, new_project.manager_ids)

        # Write - not in manager_ids, should fail
        with self.assertRaises(AccessError):
            manager_project.browse(self.project.id).write({"name": "Updated Name"})

        # Add to manager_ids - should write
        self.project.write({"manager_ids": [(4, self.manager.id)]})
        manager_project.browse(self.project.id).write({"name": "Updated Name"})
        self.assertEqual(self.project.name, "Updated Name")

    def test_manager_unlink_access(self):
        """Test manager unlink access rules"""
        # Create project as manager_2
        project = self.GitProject.with_user(self.manager_2).create(
            {"name": "Project to Delete"}
        )
        manager_project = self.GitProject.with_user(self.manager)

        # Try delete as different manager - should fail
        with self.assertRaises(AccessError):
            manager_project.browse(project.id).unlink()

        # Add to manager_ids but not creator - should fail
        project.write({"manager_ids": [(4, self.manager.id)]})
        with self.assertRaises(AccessError):
            manager_project.browse(project.id).unlink()

        # Create as manager and try delete - should succeed
        own_project = manager_project.create({"name": "Own Project"})
        self.assertTrue(own_project.exists())
        own_project.unlink()
        self.assertFalse(own_project.exists())

    def test_root_access(self):
        """Test root access rules"""
        root_project = self.GitProject.with_user(self.root)

        # Create
        new_project = root_project.create({"name": "Root Project"})
        self.assertTrue(new_project.exists())

        # Read
        self.assertEqual(root_project.browse(self.project.id).name, "Test Project")

        # Write
        root_project.browse(self.project.id).write({"name": "Updated by Root"})
        self.assertEqual(self.project.name, "Updated by Root")

        # Delete
        new_project.unlink()
        self.assertFalse(new_project.exists())

    def test_compute_user_ids(self):
        """Test computation of user_ids and manager_ids for git projects"""
        # Add users "Bob" and "user" to the group "cetmix_tower_server.group_manager"
        self.add_to_group(self.user_bob, "cetmix_tower_server.group_manager")
        self.add_to_group(self.user, "cetmix_tower_server.group_manager")

        # -- 1 --
        # Create project as manager
        project_as_manager = self.GitProject.with_user(self.manager).create(
            {
                "name": "Project As Manager",
            }
        )
        # Check that manager is added to both user_ids and manager_ids by default
        self.assertEqual(len(project_as_manager.user_ids), 1)
        self.assertIn(self.manager, project_as_manager.user_ids)
        self.assertEqual(len(project_as_manager.manager_ids), 1)
        self.assertIn(self.manager, project_as_manager.manager_ids)

        # -- 2 --
        # Create servers with multiple users and managers
        server_1 = self.Server.create(
            {
                "name": "Test Server 1",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "os_id": self.os_debian_10.id,
                "user_ids": [(6, 0, [self.user_bob.id, self.user.id])],  # Two users
                "manager_ids": [
                    (6, 0, [self.manager.id, self.manager_2.id])
                ],  # Two managers
            }
        )

        server_2 = self.Server.create(
            {
                "name": "Test Server 2",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "os_id": self.os_debian_10.id,
                "user_ids": [
                    (6, 0, [self.user_bob.id, self.user.id])
                ],  # Same two users
                "manager_ids": [
                    (6, 0, [self.manager.id, self.manager_2.id])
                ],  # Same two managers
            }
        )

        # Create project and link servers
        project = self.GitProject.create(
            {
                "name": "Test Project",
            }
        )

        # Create files and link them to the project
        for server in [server_1, server_2]:
            file = self.File.create(
                {
                    "name": f"test_file_{server.name}",
                    "server_id": server.id,
                }
            )
            self.GitProjectRel.create(
                {
                    "server_id": server.id,
                    "file_id": file.id,
                    "git_project_id": project.id,
                    "project_format": "git_aggregator",
                }
            )

        # Invalidate cache to ensure computed fields are updated
        project.invalidate_recordset(["server_ids", "user_ids", "manager_ids"])

        # -- 3 --
        # Test computed values with linked servers
        # Each user/manager should be counted only once even if present in both servers
        self.assertEqual(len(project.server_ids), 2)
        self.assertEqual(len(project.user_ids), 2)  # Two unique users
        self.assertIn(self.user_bob, project.user_ids)
        self.assertIn(self.user, project.user_ids)
        self.assertEqual(len(project.manager_ids), 2)  # Two unique managers
        self.assertIn(self.manager, project.manager_ids)
        self.assertIn(self.manager_2, project.manager_ids)

        # -- 4 --
        # Add server with different users/managers
        server_3 = self.Server.create(
            {
                "name": "Test Server 3",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "os_id": self.os_debian_10.id,
                "user_ids": [(6, 0, [self.user_bob.id])],  # Only one user
                "manager_ids": [(6, 0, [self.manager_2.id])],  # Only second manager
            }
        )
        file_3 = self.File.create(
            {
                "name": "test_file_3",
                "server_id": server_3.id,
            }
        )
        self.GitProjectRel.create(
            {
                "server_id": server_3.id,
                "file_id": file_3.id,
                "git_project_id": project.id,
                "project_format": "git_aggregator",
            }
        )

        # Invalidate cache to ensure computed fields are updated
        project.invalidate_recordset(["server_ids", "user_ids", "manager_ids"])

        # Test that computed values are updated correctly
        # Only users/managers present in all servers should remain
        self.assertEqual(len(project.server_ids), 3)
        self.assertEqual(len(project.user_ids), 1)  # Only bob is in all servers
        self.assertIn(self.user_bob, project.user_ids)
        self.assertEqual(
            len(project.manager_ids), 1
        )  # Only manager_2 is in all servers
        self.assertIn(self.manager_2, project.manager_ids)

        # -- 5 --
        # Verify that first manager can still access the project
        project_as_manager_1 = self.GitProject.with_user(self.manager).browse(
            project.id
        )
        self.assertTrue(project_as_manager_1.exists())
        self.assertEqual(project_as_manager_1.name, "Test Project")

    def test_manager_server_based_access(self):
        """Test manager access through server relationships"""
        manager_project = self.GitProject.with_user(self.manager)

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

        # Create a file and link project to server
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

        # Manager should be able to read project through server relationship
        self.assertEqual(manager_project.browse(self.project.id).name, "Test Project")

        # Remove manager from server users
        server.write({"user_ids": [(3, self.manager.id)]})

        # Manager should not be able to read project anymore
        with self.assertRaises(AccessError):
            manager_project.browse(self.project.id).read(["name"])

        # Add manager to server managers
        server.write({"manager_ids": [(4, self.manager.id)]})

        # Manager should be able to read project again
        self.assertEqual(manager_project.browse(self.project.id).name, "Test Project")
