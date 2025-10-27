from odoo.exceptions import AccessError

from .common import CommonTest


class TestFileTemplateRel(CommonTest):
    """Test class for git file template relation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.file_template_1_rel = cls.GitProjectFileTemplateRel.create(
            {
                "git_project_id": cls.git_project_1.id,
                "file_template_id": cls.file_template_1.id,
                "project_format": "git_aggregator",
            }
        )

    def test_file_template_rel_create(self):
        """Test if file template relation is created correctly"""

        # -- 1 --
        # Check if file content is updated

        # Get code from project
        yaml_code_from_project = (
            self.file_template_1_rel.git_project_id._generate_code_git_aggregator(
                self.file_template_1_rel
            )
        )

        self.assertEqual(
            self.file_template_1.code,
            yaml_code_from_project,
            "File template content is not updated correctly",
        )

        # Check specific if remote is present in file
        self.assertIn(
            self.remote_other_ssh.repo_id.url_ssh,
            self.file_template_1.code,
            "Remote is not present in file template",
        )

        # -- 2 --
        # Modify remove and check if file template content is updated
        self.remote_other_ssh.repo_id = self.Repo.create(
            {
                "url": "https://github.com/cetmix/cetmix-memes.git",
            }
        )
        self.remote_other_ssh.url_protocol = "https"

        # Must be different from previous project code
        self.assertNotEqual(
            self.file_template_1.code,
            yaml_code_from_project,
            "File template content is not updated correctly",
        )
        # New remote must be present in file
        self.assertIn(
            "https://github.com/cetmix/cetmix-memes.git",
            self.file_template_1.code,
            "Remote is not present in file template",
        )

        # -- 3 --
        # Disable source and check if file content is updated
        self.git_source_2.active = False
        self.assertNotIn(
            "https://github.com/cetmix/cetmix-memes.git",
            self.file_template_1.code,
            "Remote is present in file template",
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
            self.file_template_1_rel.git_project_id._generate_code_git_aggregator(
                self.file_template_1_rel
            )
        )
        self.assertEqual(
            yaml_code_from_project,
            yaml_code,
            "YAML code is not generated correctly",
        )

    def test_user_access(self):
        """Test that regular users have no access to git project relations"""
        user_rel = self.GitProjectFileTemplateRel.with_user(self.user)

        # Try create - should fail
        with self.assertRaises(AccessError):
            user_rel.create(
                {
                    "git_project_id": self.git_project_1.id,
                    "file_template_id": self.file_template_1.id,
                    "project_format": "git_aggregator",
                }
            )

        # Try read - should fail
        with self.assertRaises(AccessError):
            user_rel.browse(self.file_template_1_rel.id).read(["name"])

        # Try write - should fail
        with self.assertRaises(AccessError):
            user_rel.browse(self.file_template_1_rel.id).write(
                {"project_format": "git_aggregator"}
            )

        # Try unlink - should fail
        with self.assertRaises(AccessError):
            user_rel.browse(self.file_template_1_rel.id).unlink()

    def test_manager_read_access(self):
        """Test manager read access rules"""
        manager_rel = self.GitProjectFileTemplateRel.with_user(self.manager)

        # Initially manager should not have access
        with self.assertRaises(AccessError):
            manager_rel.browse(self.file_template_1_rel.id).read(["name"])

        # Add manager as project user - should have read access
        self.git_project_1.write({"user_ids": [(4, self.manager.id)]})
        self.assertEqual(
            manager_rel.browse(self.file_template_1_rel.id).name, "Git Project 1"
        )

        # Remove from project, add as file template user
        # should have read access
        self.git_project_1.write({"user_ids": [(3, self.manager.id)]})
        self.file_template_1.write({"user_ids": [(4, self.manager.id)]})
        self.assertEqual(
            manager_rel.browse(self.file_template_1_rel.id).name, "Git Project 1"
        )

        # Remove from file template users, add as project manager
        # should have read access
        self.file_template_1.write({"user_ids": [(3, self.manager.id)]})
        self.git_project_1.write({"manager_ids": [(4, self.manager.id)]})
        self.assertEqual(
            manager_rel.browse(self.file_template_1_rel.id).name, "Git Project 1"
        )

        # Remove from project, add as file template manager
        # should have read access
        self.git_project_1.write({"manager_ids": [(3, self.manager.id)]})
        self.file_template_1.write({"manager_ids": [(4, self.manager.id)]})
        self.assertEqual(
            manager_rel.browse(self.file_template_1_rel.id).name, "Git Project 1"
        )

    def test_manager_write_access(self):
        """Test manager write/create access rules"""
        manager_rel = self.GitProjectFileTemplateRel.with_user(self.manager)

        # Create new file template to avoid unique constraint violation
        file_template_2 = self.FileTemplate.create(
            {
                "name": "test_file_template_2",
            }
        )

        # Try create without being project and file template manager - should fail
        with self.assertRaises(AccessError):
            manager_rel.create(
                {
                    "git_project_id": self.git_project_1.id,
                    "file_template_id": file_template_2.id,
                    "project_format": "git_aggregator",
                }
            )

        # Add as project manager only - should still fail
        file_template_3 = self.FileTemplate.create(
            {
                "name": "test_file_template_3",
            }
        )
        self.git_project_1.write({"manager_ids": [(4, self.manager.id)]})
        with self.assertRaises(AccessError):
            manager_rel.create(
                {
                    "git_project_id": self.git_project_1.id,
                    "file_template_id": file_template_3.id,
                    "project_format": "git_aggregator",
                }
            )

        # Add as file template manager - should succeed
        file_template_4 = self.FileTemplate.create(
            {
                "name": "test_file_template_4",
            }
        )
        file_template_4.write({"manager_ids": [(4, self.manager.id)]})
        rel = manager_rel.create(
            {
                "git_project_id": self.git_project_1.id,
                "file_template_id": file_template_4.id,
                "project_format": "git_aggregator",
            }
        )
        self.assertTrue(rel.exists())

        # Test write access
        rel.write({"project_format": "git_aggregator"})

        # Remove file template manager access - should fail to write
        file_template_4.write({"manager_ids": [(3, self.manager.id)]})
        with self.assertRaises(AccessError):
            rel.write({"project_format": "git_aggregator"})

        # Remove project manager access - should fail to write
        self.git_project_1.write({"manager_ids": [(3, self.manager.id)]})
        file_template_4.write({"manager_ids": [(4, self.manager.id)]})
        with self.assertRaises(AccessError):
            rel.write({"project_format": "git_aggregator"})

    def test_manager_unlink_access(self):
        """Test manager unlink access rules"""
        manager_rel = self.GitProjectFileTemplateRel.with_user(self.manager)

        # Try delete without being project and server manager - should fail
        with self.assertRaises(AccessError):
            manager_rel.browse(self.file_template_1_rel.id).unlink()

        # Add as project manager only - should fail
        self.git_project_1.write({"manager_ids": [(4, self.manager.id)]})
        with self.assertRaises(AccessError):
            manager_rel.browse(self.file_template_1_rel.id).unlink()

        # Add as file template manager - should succeed
        self.file_template_1.write({"manager_ids": [(4, self.manager.id)]})
        self.file_template_1_rel.unlink()
        self.assertFalse(self.file_template_1_rel.exists())

    def test_root_access(self):
        """Test root access rules"""
        root_rel = self.GitProjectFileTemplateRel.with_user(self.root)

        # Create new file to avoid unique constraint violation
        file_template_3 = self.FileTemplate.create(
            {
                "name": "test_file_template_3",
            }
        )

        # Create - should succeed
        rel = root_rel.create(
            {
                "git_project_id": self.git_project_1.id,
                "file_template_id": file_template_3.id,
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
