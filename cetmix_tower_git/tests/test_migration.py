import importlib.util
import os

from odoo.tools.sql import column_exists

import odoo.addons.cetmix_tower_git as cetmix_tower_git

from .common import CommonTest

LEGACY_URL = "https://github.com/cetmix-mig/legacy-remote.git"


def _load_migrate():
    """Load ``migrate`` from the 17.0.2.0.0 post-migration script.

    Returns:
        callable: ``migrate(cr, version)`` from that script.
    """
    script_path = os.path.join(
        os.path.dirname(cetmix_tower_git.__file__),
        "migrations",
        "17.0.2.0.0",
        "post-migration.py",
    )
    spec = importlib.util.spec_from_file_location(
        "cetmix_tower_git_post_migration_17_0_2_0_0",
        script_path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.migrate


class TestGitRemoteMigration(CommonTest):
    """Post-migration from legacy remote URLs to repositories."""

    def test_migrate_skips_missing_url_column(self):
        """A 16.0 database already dropped url; cleanup must still run."""
        self.assertFalse(column_exists(self.env.cr, "cx_tower_git_remote", "url"))
        cr = self.env.cr
        cr.execute(
            """
            UPDATE cx_tower_git_remote
               SET head = CASE id
                    WHEN %s THEN 'https://github.com/cetmix/cetmix-tower/pull/42'
                    WHEN %s THEN 'feature/foo'
                    ELSE head
               END
             WHERE id IN %s
            """,
            (
                self.remote_github_https.id,
                self.remote_gitlab_https.id,
                (self.remote_github_https.id, self.remote_gitlab_https.id),
            ),
        )
        repo_before = self.remote_github_https.repo_id

        _load_migrate()(cr, "16.0.2.0.4")

        self.remote_github_https.invalidate_recordset()
        self.remote_gitlab_https.invalidate_recordset()
        self.assertEqual(self.remote_github_https.repo_id, repo_before)
        self.assertEqual(self.remote_github_https.head, "42")
        self.assertEqual(self.remote_gitlab_https.head, "feature/foo")

    def test_migrate_converts_legacy_url_column(self):
        """An earlier 17.0 database still has url and must be converted."""
        self.env.flush_all()
        cr = self.env.cr
        cr.execute("ALTER TABLE cx_tower_git_remote ADD COLUMN url VARCHAR")
        remotes = self.GitRemote.with_context(active_test=False).search([])
        cr.executemany(
            "UPDATE cx_tower_git_remote SET url = %s WHERE id = %s",
            [
                (
                    remote.repo_id.url
                    or f"https://github.com/cetmix-mig/placeholder-{remote.id}.git",
                    remote.id,
                )
                for remote in remotes
            ],
        )
        # Both remotes currently point at public repositories. The stored
        # is_private flag is what the script copies onto the new repository.
        cr.executemany(
            """
            UPDATE cx_tower_git_remote
               SET url = %s, is_private = %s
             WHERE id = %s
            """,
            [
                (LEGACY_URL, True, self.remote_github_https.id),
                (LEGACY_URL, False, self.remote_other_ssh.id),
            ],
        )
        self.GitRemote.invalidate_model()
        self.Repo.invalidate_model()

        _load_migrate()(cr, "17.0.1.0.4")

        self.remote_github_https.invalidate_recordset()
        self.remote_other_ssh.invalidate_recordset()
        repo = self.remote_github_https.repo_id
        self.assertEqual(self.remote_other_ssh.repo_id, repo)
        self.assertNotEqual(repo, self.repo_cetmix_tower)
        self.assertEqual(repo.host, "github.com")
        self.assertEqual(repo.repo, "legacy-remote")
        self.assertTrue(repo.is_private)
