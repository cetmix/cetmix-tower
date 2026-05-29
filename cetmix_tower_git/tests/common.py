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
        # Repositories
        cls.Repo = cls.env["cx.tower.git.repo"]
        cls.RepoOwner = cls.env["cx.tower.git.repo.owner"]

        cls.repo_cetmix_tower = cls.Repo.create(
            {
                "name": "Cetmix Tower",
                "url": "https://github.com/cetmix-test/cetmix-tower-test.git",
            }
        )
        cls.repo_oca_web = cls.Repo.create(
            {
                "name": "OCA Web",
                "url": "https://github.com/oca-test/web-test.git",
            }
        )
        cls.repo_odoo_enterprise = cls.Repo.create(
            {
                "name": "Odoo Enterprise",
                "url": "https://github.com/odoo-test/enterprise-test.git",
                "is_private": True,
            }
        )
        cls.repo_gitlab_private = cls.Repo.create(
            {
                "name": "GitLab Private",
                "url": "git@my.gitlab.com:cetmix-test/cetmix-tower-test.git",
                "is_private": True,
            }
        )
        cls.repo_bitbucket_private = cls.Repo.create(
            {
                "name": "Bitbucket Private",
                "url": "https://bitbucket.com/cetmix-test/cetmix-tower-test-enterprise.git",
                "is_private": True,
            }
        )

        # Same urls, different protocols (intentionally aliased)
        cls.repo_other_ssh = cls.Repo.create(
            {"url": "git@memegit.com:cetmix-test/cetmix-tower-test.git"}
        )
        cls.repo_other_https = cls.repo_other_ssh

        # Remotes
        cls.remote_github_https = cls.GitRemote.create(
            {
                "repo_id": cls.repo_cetmix_tower.id,
                "source_id": cls.git_source_1.id,
                "head_type": "pr",
                "head": "https://github.com/cetmix-test/cetmix-tower-test/pull/123",
                "sequence": 1,
            }
        )
        cls.remote_gitlab_https = cls.GitRemote.create(
            {
                "repo_id": cls.repo_gitlab_private.id,
                "source_id": cls.git_source_1.id,
                "head_type": "branch",
                "head": "main",
                "sequence": 2,
            }
        )
        cls.remote_gitlab_ssh = cls.GitRemote.create(
            {
                "repo_id": cls.repo_gitlab_private.id,
                "source_id": cls.git_source_1.id,
                "head_type": "commit",
                "url_protocol": "ssh",
                "head": "10000000",
                "sequence": 3,
            }
        )
        cls.remote_bitbucket_https = cls.GitRemote.create(
            {
                "repo_id": cls.repo_bitbucket_private.id,
                "source_id": cls.git_source_2.id,
                "head_type": "branch",
                "head": "dev",
                "sequence": 4,
            }
        )
        cls.remote_other_ssh = cls.GitRemote.create(
            {
                "repo_id": cls.repo_other_ssh.id,
                "source_id": cls.git_source_2.id,
                "head_type": "branch",
                "url_protocol": "ssh",
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
