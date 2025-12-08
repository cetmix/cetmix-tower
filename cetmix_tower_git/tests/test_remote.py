from odoo.exceptions import AccessError

from .common import CommonTest


class TestRemote(CommonTest):
    """Test class for git remote."""

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
        cls.repo_cetmix_tower = cls.Repo.create(
            {
                "name": "Cetmix Tower",
                "url": "https://github.com/cetmix-test/cetmix-tower.git",
            }
        )
        cls.remote = cls.GitRemote.create(
            {
                "repo_id": cls.repo_cetmix_tower.id,
                "source_id": cls.source.id,
                "head_type": "branch",
                "head": "main",
            }
        )
        cls.repo_test = cls.Repo.create(
            {
                "name": "Test Repository",
                "url": "https://github.com/cetmix-test/test.git",
            }
        )

    def test_user_access(self):
        """Test that regular users have no access to git remotes"""
        user_remote = self.GitRemote.with_user(self.user)

        # Test CRUD operations
        with self.assertRaises(AccessError):
            user_remote.create(
                {
                    "repo_id": self.repo_test.id,
                    "url_protocol": "https",
                    "source_id": self.source.id,
                    "head": "main",
                }
            )
        with self.assertRaises(AccessError):
            user_remote.search([("id", "=", self.remote.id)])
        with self.assertRaises(AccessError):
            self.remote.with_user(self.user).write({"head": "dev"})
        with self.assertRaises(AccessError):
            self.remote.with_user(self.user).unlink()

    def test_manager_read_access(self):
        """Test manager read access rules"""
        manager_remote = self.GitRemote.with_user(self.manager)

        # Manager not in project user_ids or manager_ids - should not read
        self.assertFalse(manager_remote.search([("id", "=", self.remote.id)]))

        # Add manager to project user_ids - should read
        self.project.write({"user_ids": [(4, self.manager.id)]})
        remote = manager_remote.search([("id", "=", self.remote.id)])
        self.assertTrue(remote)
        self.assertEqual(remote.head, "main")

        # Remove from user_ids, add to manager_ids - should read
        self.project.write(
            {"user_ids": [(3, self.manager.id)], "manager_ids": [(4, self.manager.id)]}
        )
        remote = manager_remote.search([("id", "=", self.remote.id)])
        self.assertTrue(remote.exists())

    def test_manager_write_access(self):
        """Test manager write/create access rules"""
        manager_remote = self.GitRemote.with_user(self.manager)

        # Create project as manager - should be added to manager_ids automatically
        project = self.GitProject.with_user(self.manager).create(
            {
                "name": "Manager Project",
            }
        )
        source = self.GitSource.with_user(self.manager).create(
            {
                "name": "Manager Source",
                "git_project_id": project.id,
            }
        )

        # Create remote in own project - should succeed
        new_remote = manager_remote.create(
            {
                "repo_id": self.repo_test.id,
                "url_protocol": "https",
                "source_id": source.id,
                "head_type": "branch",
                "head": "main",
            }
        )
        self.assertTrue(new_remote.exists())

        # Write to own remote - should succeed
        new_remote.write({"head": "dev"})
        self.assertEqual(new_remote.head, "dev")

        # Write to other's remote - should fail
        with self.assertRaises(AccessError):
            self.remote.with_user(self.manager).write({"head": "dev"})

    def test_manager_unlink_access(self):
        """Test manager unlink access rules"""
        # Create project and remote as manager_2
        project = self.GitProject.with_user(self.manager_2).create(
            {
                "name": "Manager 2 Project",
            }
        )
        source = self.GitSource.create(
            {
                "name": "Manager 2 Source",
                "git_project_id": project.id,
            }
        )
        remote = self.GitRemote.with_user(self.manager_2).create(
            {
                "repo_id": self.repo_test.id,
                "url_protocol": "https",
                "source_id": source.id,
                "head_type": "branch",
                "head": "main",
            }
        )

        # Try delete as different manager - should fail even if added to manager_ids
        project.write({"manager_ids": [(4, self.manager.id)]})
        with self.assertRaises(AccessError):
            remote.with_user(self.manager).unlink()

        # Create remote as manager and try delete - should succeed
        own_remote = self.GitRemote.with_user(self.manager).create(
            {
                "repo_id": self.repo_test.id,
                "url_protocol": "https",
                "source_id": source.id,
                "head_type": "branch",
                "head": "main",
            }
        )
        self.assertTrue(own_remote.exists())
        own_remote.with_user(self.manager).unlink()
        self.assertFalse(own_remote.exists())

    def test_root_access(self):
        """Test root access rules"""
        root_remote = self.GitRemote.with_user(self.root)

        # Create
        new_remote = root_remote.create(
            {
                "repo_id": self.repo_test.id,
                "url_protocol": "https",
                "source_id": self.source.id,
                "head_type": "branch",
                "head": "main",
            }
        )
        self.assertTrue(new_remote.exists())

        # Read
        remote = root_remote.search([("id", "=", self.remote.id)])
        self.assertTrue(remote)
        self.assertEqual(remote.head, "main")

        # Write
        self.remote.with_user(self.root).write({"head": "dev"})
        self.assertEqual(self.remote.head, "dev")

        # Delete
        new_remote.with_user(self.root).unlink()
        self.assertFalse(new_remote.exists())

    def test_remote_provider_protocol_and_name(self):
        """Test if remote provider is detected correctly"""

        # -- 1--
        # GitHub + https
        # Check if remote provider is detected correctly
        self.assertEqual(
            self.remote_github_https.repo_provider,
            "github",
            "Provider is not detected correctly",
        )
        self.assertEqual(
            self.remote_github_https.url_protocol,
            "https",
            "Protocol is not detected correctly",
        )
        self.assertEqual(
            self.remote_github_https.name,
            "remote_1",
            "Name is not prepared correctly",
        )

        # -- 2 --
        # GitLab + ssh
        # Check if remote provider is detected correctly
        self.assertEqual(
            self.remote_gitlab_ssh.repo_provider,
            "gitlab",
            "Provider is not detected correctly",
        )
        self.assertEqual(
            self.remote_gitlab_ssh.url_protocol,
            "ssh",
            "Protocol is not detected correctly",
        )
        self.assertEqual(
            self.remote_gitlab_ssh.name,
            "remote_3",
            "Name is not prepared correctly",
        )

        # -- 3 --
        # Bitbucket + https
        # Check if remote provider is detected correctly
        self.assertEqual(
            self.remote_bitbucket_https.repo_provider,
            "bitbucket",
            "Provider is not detected correctly",
        )
        self.assertEqual(
            self.remote_bitbucket_https.url_protocol,
            "https",
            "Protocol is not detected correctly",
        )
        self.assertEqual(
            self.remote_bitbucket_https.name,
            "remote_1",
            "Name is not prepared correctly",
        )

        # -- 4 --
        # Other + ssh
        # Check if remote provider is detected correctly
        self.assertEqual(
            self.remote_other_ssh.repo_provider,
            "gitlab",  # this is how giturlparse detects the provider
            "Provider is not detected correctly",
        )
        self.assertEqual(
            self.remote_other_ssh.url_protocol,
            "ssh",
            "Protocol is not detected correctly",
        )
        self.assertEqual(
            self.remote_other_ssh.name,
            "remote_2",
            "Name is not prepared correctly",
        )

    def test_git_aggregator_prepare_url(self):
        """Test if url is prepared correctly"""

        # -- 1 --
        # GitHub + https
        self.remote_github_https.repo_id.is_private = False
        self.assertEqual(
            self.remote_github_https._git_aggregator_prepare_url(),
            self.remote_github_https.repo_id.url,
            "URL is not prepared correctly",
        )

        # -- 2 --
        # GitHub + https -> private
        self.remote_github_https.repo_id.is_private = True
        self.assertEqual(
            self.remote_github_https._git_aggregator_prepare_url(),
            "https://$GITHUB_TOKEN:x-oauth-basic@github.com/cetmix-test/cetmix-tower-test.git",
            "URL is not prepared correctly",
        )

        # -- 3 --
        # Gitlab + https
        self.remote_gitlab_https.repo_id.is_private = False
        self.assertEqual(
            self.remote_gitlab_https._git_aggregator_prepare_url(),
            self.remote_gitlab_https.repo_id.url,
            "URL is not prepared correctly",
        )

        # -- 4 --
        # Gitlab + https -> private
        self.remote_gitlab_https.repo_id.is_private = True
        self.assertEqual(
            self.remote_gitlab_https._git_aggregator_prepare_url(),
            "https://$GITLAB_TOKEN_NAME:$GITLAB_TOKEN@my.gitlab.com/cetmix-test/cetmix-tower-test.git",
            "URL is not prepared correctly",
        )

        # -- 5 --
        # Bitbucket + https
        self.remote_bitbucket_https.repo_id.is_private = False
        self.assertEqual(
            self.remote_bitbucket_https._git_aggregator_prepare_url(),
            self.remote_bitbucket_https.repo_id.url,
            "URL is not prepared correctly",
        )

        # -- 6 --
        # Bitbucket + https -> private
        self.remote_bitbucket_https.repo_id.is_private = True
        self.assertEqual(
            self.remote_bitbucket_https._git_aggregator_prepare_url(),
            "https://x-token-auth:$BITBUCKET_TOKEN@bitbucket.com/cetmix-test/cetmix-tower-test-enterprise.git",
            "URL is not prepared correctly",
        )

        # -- 7 --
        # Other + ssh
        self.remote_other_ssh.repo_id.is_private = False
        self.assertEqual(
            self.remote_other_ssh._git_aggregator_prepare_url(),
            self.remote_other_ssh.repo_id.url_ssh,
            "URL is not prepared correctly",
        )

    def test_git_aggregator_prepare_head(self):
        """Test if head is prepared correctly"""

        # -- 1 --
        # GitHub + PR/MR as link
        self.assertEqual(
            self.remote_github_https._git_aggregator_prepare_head(),
            "refs/pull/123/head",
            "Head is not prepared correctly",
        )

        # -- 2 --
        # GitHub + PR/MR as number
        self.remote_github_https.write({"head": "123", "head_type": "pr"})
        self.assertEqual(
            self.remote_github_https._git_aggregator_prepare_head(),
            "refs/pull/123/head",
            "Head is not prepared correctly",
        )

        # -- 3 --
        # GitHub + branch as name
        self.remote_github_https.write({"head": "main", "head_type": "branch"})
        self.assertEqual(
            self.remote_github_https._git_aggregator_prepare_head(),
            self.remote_github_https.head,
            "Head is not prepared correctly",
        )

        # -- 4 --
        # GitHub + branch as link
        self.remote_github_https.write(
            {
                "head": "https://github.com/cetmix-test/cetmix-tower/list/14.0-demo-branch",
                "head_type": "branch",
            }
        )
        self.assertEqual(
            self.remote_github_https._git_aggregator_prepare_head(),
            "14.0-demo-branch",
            "Head is not prepared correctly",
        )

        # -- 5 --
        # GitHub + commit as number
        self.remote_github_https.write({"head": "1234567890", "head_type": "commit"})
        self.assertEqual(
            self.remote_github_https._git_aggregator_prepare_head(),
            "1234567890",
            "Head is not prepared correctly",
        )

        # -- 6 --
        # GitHub + commit as link
        self.remote_github_https.head = (
            "https://github.com/cetmix-test/cetmix-tower/commit/1234567890"
        )
        self.assertEqual(
            self.remote_github_https._git_aggregator_prepare_head(),
            "1234567890",
            "Head is not prepared correctly",
        )

    def test_manager_server_based_access(self):
        """Test manager access to remotes through server relationships"""
        manager_remote = self.GitRemote.with_user(self.manager)

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

        # Manager should be able to read remote through server relationship
        remote = manager_remote.search([("id", "=", self.remote.id)])
        self.assertTrue(remote)
        self.assertEqual(remote.head, "main")

        # Remove manager from server users
        server.write({"user_ids": [(3, self.manager.id)]})

        # Manager should not be able to read remote anymore
        self.assertFalse(manager_remote.search([("id", "=", self.remote.id)]))

        # Add manager to server managers
        server.write({"manager_ids": [(4, self.manager.id)]})

        # Manager should be able to read remote again
        remote = manager_remote.search([("id", "=", self.remote.id)])
        self.assertTrue(remote)
        self.assertEqual(remote.head, "main")
