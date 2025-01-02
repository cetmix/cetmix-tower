from odoo.addons.cetmix_tower_server.tests.common import TestTowerCommon


class CommonTest(TestTowerCommon):
    """Common test class for all tests."""

    def setUp(self):
        super().setUp()

        # Models
        self.GitProject = self.env["cx.tower.git.project"]
        self.GitProjectRel = self.env["cx.tower.git.project.rel"]
        self.GitSource = self.env["cx.tower.git.source"]
        self.GitRemote = self.env["cx.tower.git.remote"]

        # Data
        # Project
        self.git_project_1 = self.GitProject.create({"name": "Git Project 1"})

        # Sources
        self.git_source_1 = self.GitSource.create(
            {"name": "Git Source 1", "git_project_id": self.git_project_1.id}
        )
        self.git_source_2 = self.GitSource.create(
            {"name": "Git Source 2", "git_project_id": self.git_project_1.id}
        )

        # Remotes
        self.remote_github_https = self.GitRemote.create(
            {
                "url": "https://github.com/cetmix/cetmix-tower.git",
                "source_id": self.git_source_1.id,
                "head_type": "pr",
                "head": "https://github.com/cetmix/cetmix-tower/pull/123",
                "sequence": 1,
            }
        )
        self.remote_gitlab_https = self.GitRemote.create(
            {
                "url": "https://gitlab.com/cetmix/cetmix-tower.git",
                "source_id": self.git_source_1.id,
                "head_type": "branch",
                "head": "main",
                "sequence": 2,
            }
        )
        self.remote_gitlab_ssh = self.GitRemote.create(
            {
                "url": "git@my.gitlab.org:cetmix/cetmix-tower.git",
                "source_id": self.git_source_1.id,
                "head_type": "commit",
                "head": "10000000",
                "sequence": 3,
            }
        )
        self.remote_bitbucket_https = self.GitRemote.create(
            {
                "url": "https://bitbucket.org/cetmix/cetmix-tower.git",
                "source_id": self.git_source_2.id,
                "head": "dev",
                "sequence": 4,
            }
        )
        self.remote_other_ssh = self.GitRemote.create(
            {
                "url": "git@other.com:cetmix/cetmix-tower.git",
                "source_id": self.git_source_2.id,
                "head": "old",
                "sequence": 5,
            }
        )

        # File
        self.server_1_file_1 = self.File.create(
            {
                "name": "File 1",
                "server_id": self.server_test_1.id,
                "source": "tower",
            }
        )
