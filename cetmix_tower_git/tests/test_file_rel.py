from odoo.exceptions import AccessError

from .common import CommonTest


class TestFileRel(CommonTest):
    """Test class for git file relation."""

    def setUp(self):
        super().setUp()
        self.file_1_rel = self.GitProjectRel.create(
            {
                "server_id": self.server_test_1.id,
                "file_id": self.server_1_file_1.id,
                "git_project_id": self.git_project_1.id,
                "project_format": "git_aggregator",
            }
        )

    def test_file_rel_create(self):
        """Test if file relation is created correctly"""

        # -- 1 --
        # Check if file content is updated

        # Get code from project
        yaml_code_from_project = (
            self.file_1_rel.git_project_id._generate_code_git_aggregator(
                self.file_1_rel
            )
        )

        self.assertEqual(
            self.server_1_file_1.code,
            yaml_code_from_project,
            "File content is not updated correctly",
        )

        # Check specific if remote is present in file
        self.assertIn(
            self.remote_other_ssh.repo_id.url_ssh,
            self.server_1_file_1.code,
            "Remote is not present in file",
        )

        # -- 2 --
        # Modify remove and check if file content is updated
        self.remote_other_ssh.repo_id = self.Repo.create(
            {
                "url": "https://github.com/cetmix/cetmix-memes.git",
            }
        )
        self.remote_other_ssh.url_protocol = "https"

        # Must be different from previous project code
        self.assertNotEqual(
            self.server_1_file_1.code,
            yaml_code_from_project,
            "File content is not updated correctly",
        )
        # New remote must be present in file
        self.assertIn(
            "https://github.com/cetmix/cetmix-memes.git",
            self.server_1_file_1.code,
            "Remote is not present in file",
        )

        # -- 3 --
        # Disable source and check if file content is updated
        self.git_source_2.active = False
        self.assertNotIn(
            "https://github.com/cetmix/cetmix-memes.git",
            self.server_1_file_1.code,
            "Remote is present in file",
        )

    def test_format_git_aggregator(self):
        """Test if format git aggregator works correctly"""

        # -- 1 --
        # Check if YAML code is generated correctly

        yaml_code = """# This file is generated with Cetmix Tower https://cetmix.com/tower
# It's designed to be used with git-aggregator tool developed by Acsone.
# Documentation for git-aggregator: https://github.com/acsone/git-aggregator

# You need to set the following variables in your environment:
# BITBUCKET_TOKEN, GITLAB_TOKEN, GITLAB_TOKEN_NAME
# and run git-aggregator with '--expand-env' parameter.

./git_project_1_git_source_1:
  remotes:
    remote_1: https://github.com/cetmix-test/cetmix-tower-test.git
    remote_2: https://$GITLAB_TOKEN_NAME:$GITLAB_TOKEN@my.gitlab.com/cetmix-test/cetmix-tower-test.git
    remote_3: git@my.gitlab.com:cetmix-test/cetmix-tower-test.git
  merges:
  - remote: remote_1
    ref: refs/pull/123/head
  - remote: remote_2
    ref: main
  - remote: remote_3
    ref: '10000000'
  target: remote_1
./git_project_1_git_source_1_2:
  remotes:
    remote_1: https://x-token-auth:$BITBUCKET_TOKEN@bitbucket.com/cetmix-test/cetmix-tower-test-enterprise.git
    remote_2: git@memegit.com:cetmix-test/cetmix-tower-test.git
  merges:
  - remote: remote_1
    ref: dev
  - remote: remote_2
    ref: old
  target: remote_1
"""  # noqa: E501

        # Get code from project
        yaml_code_from_project = (
            self.file_1_rel.git_project_id._generate_code_git_aggregator(
                self.file_1_rel
            )
        )
        self.assertEqual(
            yaml_code_from_project,
            yaml_code,
            "YAML code is not generated correctly",
        )

        # -- 2 --
        # Unlink remote and check if file content is updated
        self.remote_github_https.unlink()
        yaml_code_from_project = (
            self.file_1_rel.git_project_id._generate_code_git_aggregator(
                self.file_1_rel
            )
        )
        yaml_code = """# This file is generated with Cetmix Tower https://cetmix.com/tower
# It's designed to be used with git-aggregator tool developed by Acsone.
# Documentation for git-aggregator: https://github.com/acsone/git-aggregator

# You need to set the following variables in your environment:
# BITBUCKET_TOKEN, GITLAB_TOKEN, GITLAB_TOKEN_NAME
# and run git-aggregator with '--expand-env' parameter.

./git_project_1_git_source_1:
  remotes:
    remote_2: https://$GITLAB_TOKEN_NAME:$GITLAB_TOKEN@my.gitlab.com/cetmix-test/cetmix-tower-test.git
    remote_3: git@my.gitlab.com:cetmix-test/cetmix-tower-test.git
  merges:
  - remote: remote_2
    ref: main
  - remote: remote_3
    ref: '10000000'
  target: remote_2
./git_project_1_git_source_1_2:
  remotes:
    remote_1: https://x-token-auth:$BITBUCKET_TOKEN@bitbucket.com/cetmix-test/cetmix-tower-test-enterprise.git
    remote_2: git@memegit.com:cetmix-test/cetmix-tower-test.git
  merges:
  - remote: remote_1
    ref: dev
  - remote: remote_2
    ref: old
  target: remote_1
"""  # noqa: E501

        self.assertEqual(
            yaml_code_from_project,
            yaml_code,
            "YAML code is not generated correctly",
        )

        # -- 3 --
        # Unlink source and check if file content is updated
        self.git_source_2.unlink()
        yaml_code_from_project = (
            self.file_1_rel.git_project_id._generate_code_git_aggregator(
                self.file_1_rel
            )
        )
        yaml_code = """# This file is generated with Cetmix Tower https://cetmix.com/tower
# It's designed to be used with git-aggregator tool developed by Acsone.
# Documentation for git-aggregator: https://github.com/acsone/git-aggregator

# You need to set the following variables in your environment:
# GITLAB_TOKEN, GITLAB_TOKEN_NAME
# and run git-aggregator with '--expand-env' parameter.

./git_project_1_git_source_1:
  remotes:
    remote_2: https://$GITLAB_TOKEN_NAME:$GITLAB_TOKEN@my.gitlab.com/cetmix-test/cetmix-tower-test.git
    remote_3: git@my.gitlab.com:cetmix-test/cetmix-tower-test.git
  merges:
  - remote: remote_2
    ref: main
  - remote: remote_3
    ref: '10000000'
  target: remote_2
"""  # noqa: E501
        self.assertEqual(
            yaml_code_from_project,
            yaml_code,
            "YAML code is not generated correctly",
        )

    def test_user_access(self):
        """Test that regular users have no access to git project relations"""
        user_rel = self.GitProjectRel.with_user(self.user)

        # Try create - should fail
        with self.assertRaises(AccessError):
            user_rel.create(
                {
                    "server_id": self.server_test_1.id,
                    "file_id": self.server_1_file_1.id,
                    "git_project_id": self.git_project_1.id,
                    "project_format": "git_aggregator",
                }
            )

        # Try read - should fail
        with self.assertRaises(AccessError):
            user_rel.browse(self.file_1_rel.id).read(["name"])

        # Try write - should fail
        with self.assertRaises(AccessError):
            user_rel.browse(self.file_1_rel.id).write(
                {"project_format": "git_aggregator"}
            )

        # Try unlink - should fail
        with self.assertRaises(AccessError):
            user_rel.browse(self.file_1_rel.id).unlink()

    def test_manager_read_access(self):
        """Test manager read access rules"""
        manager_rel = self.GitProjectRel.with_user(self.manager)

        # Initially manager should not have access
        with self.assertRaises(AccessError):
            manager_rel.browse(self.file_1_rel.id).read(["name"])

        # Add manager as project user - should have read access
        self.git_project_1.write({"user_ids": [(4, self.manager.id)]})
        self.assertEqual(manager_rel.browse(self.file_1_rel.id).name, "Git Project 1")

        # Remove from project, add as server user - should have read access
        self.git_project_1.write({"user_ids": [(3, self.manager.id)]})
        self.server_test_1.write({"user_ids": [(4, self.manager.id)]})
        self.assertEqual(manager_rel.browse(self.file_1_rel.id).name, "Git Project 1")

        # Remove from server users, add as project manager - should have read access
        self.server_test_1.write({"user_ids": [(3, self.manager.id)]})
        self.git_project_1.write({"manager_ids": [(4, self.manager.id)]})
        self.assertEqual(manager_rel.browse(self.file_1_rel.id).name, "Git Project 1")

        # Remove from project, add as server manager - should have read access
        self.git_project_1.write({"manager_ids": [(3, self.manager.id)]})
        self.server_test_1.write({"manager_ids": [(4, self.manager.id)]})
        self.assertEqual(manager_rel.browse(self.file_1_rel.id).name, "Git Project 1")

    def test_manager_write_access(self):
        """Test manager write/create access rules"""
        manager_rel = self.GitProjectRel.with_user(self.manager)

        # Create new file to avoid unique constraint violation
        file_2 = self.File.create(
            {
                "name": "test_file_2",
                "server_id": self.server_test_1.id,
                "source": "tower",
                "file_type": "text",
            }
        )

        # Try create without being project and server manager - should fail
        with self.assertRaises(AccessError):
            manager_rel.create(
                {
                    "server_id": self.server_test_1.id,
                    "file_id": file_2.id,
                    "git_project_id": self.git_project_1.id,
                    "project_format": "git_aggregator",
                }
            )

        # Add as project manager only - should still fail
        file_3 = self.File.create(
            {
                "name": "test_file_3",
                "server_id": self.server_test_1.id,
                "source": "tower",
                "file_type": "text",
            }
        )
        self.git_project_1.write({"manager_ids": [(4, self.manager.id)]})
        with self.assertRaises(AccessError):
            manager_rel.create(
                {
                    "server_id": self.server_test_1.id,
                    "file_id": file_3.id,
                    "git_project_id": self.git_project_1.id,
                    "project_format": "git_aggregator",
                }
            )

        # Add as server manager - should succeed
        file_4 = self.File.create(
            {
                "name": "test_file_4",
                "server_id": self.server_test_1.id,
                "source": "tower",
                "file_type": "text",
            }
        )
        self.server_test_1.write({"manager_ids": [(4, self.manager.id)]})
        rel = manager_rel.create(
            {
                "server_id": self.server_test_1.id,
                "file_id": file_4.id,
                "git_project_id": self.git_project_1.id,
                "project_format": "git_aggregator",
            }
        )
        self.assertTrue(rel.exists())

        # Test write access
        rel.write({"project_format": "git_aggregator"})

        # Remove server manager access - should fail to write
        self.server_test_1.write({"manager_ids": [(3, self.manager.id)]})
        with self.assertRaises(AccessError):
            rel.write({"project_format": "git_aggregator"})

        # Remove project manager access - should fail to write
        self.git_project_1.write({"manager_ids": [(3, self.manager.id)]})
        with self.assertRaises(AccessError):
            rel.write({"project_format": "git_aggregator"})

    def test_manager_unlink_access(self):
        """Test manager unlink access rules"""
        manager_rel = self.GitProjectRel.with_user(self.manager)

        # Try delete without being project and server manager - should fail
        with self.assertRaises(AccessError):
            manager_rel.browse(self.file_1_rel.id).unlink()

        # Add as project manager only - should fail
        self.git_project_1.write({"manager_ids": [(4, self.manager.id)]})
        with self.assertRaises(AccessError):
            manager_rel.browse(self.file_1_rel.id).unlink()

        # Add as server manager - should succeed
        self.server_test_1.write({"manager_ids": [(4, self.manager.id)]})
        self.file_1_rel.with_user(self.manager).unlink()
        self.assertFalse(self.file_1_rel.exists())

    def test_root_access(self):
        """Test root access rules"""
        root_rel = self.GitProjectRel.with_user(self.root)

        # Create new file to avoid unique constraint violation
        file_3 = self.File.create(
            {
                "name": "test_file_3",
                "server_id": self.server_test_1.id,
                "source": "tower",
                "file_type": "text",
            }
        )

        # Create - should succeed
        rel = root_rel.create(
            {
                "server_id": self.server_test_1.id,
                "file_id": file_3.id,
                "git_project_id": self.git_project_1.id,
                "project_format": "git_aggregator",
            }
        )
        self.assertTrue(rel.exists())

        # Read - should succeed
        self.assertEqual(root_rel.browse(rel.id).name, "Git Project 1")

        # Write - should succeed
        root_rel.browse(rel.id).write({"project_format": "git_aggregator"})

        # Delete - should succeed
        rel.unlink()
        self.assertFalse(rel.exists())
