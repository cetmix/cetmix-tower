# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from .common import CommonTest


class TestTowerGitShortcut(CommonTest):
    """Ensure the cetmix.tower shortcut delegates correctly."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Link the Git project to Server 1 so the lookup can find it
        cls.GitProjectRel.create(
            {
                "git_project_id": cls.git_project_1.id,
                "server_id": cls.server_test_1.id,
                "file_id": cls.server_1_file_1.id,
            }
        )

    def test_shortcut_returns_same_servers(self):
        """Shortcut must return exactly the same servers as the model API."""
        url = self.remote_github_https.url
        head = self.remote_github_https.head
        head_type = self.remote_github_https.head_type

        servers_model = self.env["cx.tower.server"].get_servers_by_git_ref(
            url, head, head_type
        )
        servers_shortcut = self.env["cetmix.tower"].server_get_by_git_ref(
            url, head, head_type
        )
        self.assertCountEqual(servers_model.ids, servers_shortcut.ids)
