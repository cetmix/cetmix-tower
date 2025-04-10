from odoo.addons.cetmix_tower_server.tests.common import TestTowerCommon


class CommonTest(TestTowerCommon):
    """Common test class for all tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Models
        cls.GitProject = cls.env["cx.tower.git.project"]
        cls.GitProjectRel = cls.env["cx.tower.git.project.rel"]
        cls.GitProjectFileTemplateRel = cls.env[
            "cx.tower.git.project.file.template.rel"
        ]
        cls.GitSource = cls.env["cx.tower.git.source"]
        cls.GitRemote = cls.env["cx.tower.git.remote"]

        # Data
        # Project
        cls.git_project_1 = cls.GitProject.create({"name": "Git Project 1"})

        # Sources
        cls.git_source_1 = cls.GitSource.create(
            {"name": "Git Source 1", "git_project_id": cls.git_project_1.id}
        )
        cls.git_source_2 = cls.GitSource.create(
            {"name": "Git Source 2", "git_project_id": cls.git_project_1.id}
        )

        # Remotes
        cls.remote_github_https = cls.GitRemote.create(
            {
                "url": "https://github.com/cetmix/cetmix-tower.git",
                "source_id": cls.git_source_1.id,
                "head_type": "pr",
                "head": "https://github.com/cetmix/cetmix-tower/pull/123",
                "sequence": 1,
            }
        )
        cls.remote_gitlab_https = cls.GitRemote.create(
            {
                "url": "https://gitlab.com/cetmix/cetmix-tower.git",
                "source_id": cls.git_source_1.id,
                "head_type": "branch",
                "head": "main",
                "sequence": 2,
            }
        )
        cls.remote_gitlab_ssh = cls.GitRemote.create(
            {
                "url": "git@my.gitlab.org:cetmix/cetmix-tower.git",
                "source_id": cls.git_source_1.id,
                "head_type": "commit",
                "head": "10000000",
                "sequence": 3,
            }
        )
        cls.remote_bitbucket_https = cls.GitRemote.create(
            {
                "url": "https://bitbucket.org/cetmix/cetmix-tower.git",
                "source_id": cls.git_source_2.id,
                "head": "dev",
                "sequence": 4,
            }
        )
        cls.remote_other_ssh = cls.GitRemote.create(
            {
                "url": "pepefrog@memegit.com:cetmix/cetmix-tower.git",
                "source_id": cls.git_source_2.id,
                "head": "old",
                "sequence": 5,
            }
        )

        # File
        cls.server_1_file_1 = cls.File.create(
            {
                "name": "File 1",
                "server_id": cls.server_test_1.id,
                "source": "tower",
            }
        )
        cls.file_template_1 = cls.FileTemplate.create(
            {
                "name": "File Template 1",
            }
        )
