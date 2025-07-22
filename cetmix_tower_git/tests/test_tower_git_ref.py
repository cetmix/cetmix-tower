# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from .common import CommonTest


class TestGetServersByGitRef(CommonTest):
    """Unit tests for cx.tower.server.get_servers_by_git_ref()."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # canonical repo URL used in the tests
        cls.repo_slug = "testorg/test_repo_123"
        cls.canonical = f"https://github.com/{cls.repo_slug}.git"

        # Git objects
        GitProject = cls.GitProject
        GitSource = cls.GitSource
        GitRemote = cls.GitRemote
        GitProjRel = cls.GitProjectRel
        File = cls.File

        cls.project = GitProject.create({"name": "Demo"})
        cls.src = GitSource.create(
            {
                "name": "Local",
                "git_project_id": cls.project.id,
            }
        )

        GitRemote.create(
            {
                "git_project_id": cls.project.id,
                "source_id": cls.src.id,
                "url": cls.canonical,
                "head": "main",
                "head_type": "branch",
            }
        )

        file = File.create(
            {
                "server_id": cls.server_test_1.id,
                "source": "tower",
                "file_type": "text",
                "name": "dummy.txt",
            }
        )
        GitProjRel.create(
            {
                "git_project_id": cls.project.id,
                "server_id": cls.server_test_1.id,
                "file_id": file.id,
            }
        )

    # Positive
    def test_success(self):
        """Canonical URL must return the linked server."""
        servers = self.Server.get_servers_by_git_ref(self.canonical, "main", "branch")
        self.assertEqual(servers, self.server_test_1)

    # Negative
    def test_no_match(self):
        """Foreign repo URL must return an empty recordset."""
        other = "https://github.com/another/repo.git"
        servers = self.Server.get_servers_by_git_ref(other, "main", "branch")
        self.assertFalse(servers)
