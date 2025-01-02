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
        yaml_code_from_project = self.file_1_rel._generate_code_git_aggregator(
            self.file_1_rel
        )

        self.assertEqual(
            self.server_1_file_1.code,
            yaml_code_from_project,
            "File content is not updated correctly",
        )

        # Check specific if remote is present in file
        self.assertIn(
            self.remote_other_ssh.url,
            self.server_1_file_1.code,
            "Remote is not present in file",
        )

        # -- 2 --
        # Modify remove and check if file content is updated
        self.remote_other_ssh.url = "https://github.com/cetmix/cetmix-memes.git"

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

./git_project_1_git_source_1:
  remotes:
    remote_1: https://github.com/cetmix/cetmix-tower.git
    remote_2: https://gitlab.com/cetmix/cetmix-tower.git
    remote_3: git@my.gitlab.org:cetmix/cetmix-tower.git
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
    remote_1: https://bitbucket.org/cetmix/cetmix-tower.git
    remote_2: git@other.com:cetmix/cetmix-tower.git
  merges:
  - remote: remote_1
    ref: dev
  - remote: remote_2
    ref: old
  target: remote_1
"""  # noqa: E501

        # Get code from project
        yaml_code_from_project = self.file_1_rel._generate_code_git_aggregator(
            self.file_1_rel
        )
        self.assertEqual(
            yaml_code_from_project,
            yaml_code,
            "YAML code is not generated correctly",
        )
