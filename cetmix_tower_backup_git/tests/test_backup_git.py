# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo.addons.cetmix_tower_backup.tests.test_backup import BackupCommon


class TestBackupGit(BackupCommon):
    """Exercise bridge behavior with real Git records and Python Restore plans."""

    def test_git_snapshot_restores_fresh_grouped_sources_before_plan(self):
        self.template.use_git_projects = True
        project = self.env["cx.tower.git.project"]._create_named_git_project(
            "Source project"
        )
        project.write(
            {"git_aggregator_root_dir": "/srv/git", "note": "Backup Git note"}
        )
        source = self.env["cx.tower.git.source"].create(
            {
                "git_project_id": project.id,
                "name": "Grouped source",
                "sequence": 11,
                "enabled": False,
            }
        )
        repo_model = self.env["cx.tower.git.repo"]
        remotes = self.env["cx.tower.git.remote"]
        for url in (
            "https://github.com/cetmix/cetmix-tower",
            "https://github.com/OCA/server-tools",
        ):
            repo_id = repo_model._get_repo_id_by_url(
                url, create=True, raise_if_invalid=True
            )
            remotes.create(
                {
                    "source_id": source.id,
                    "repo_id": repo_id,
                    "head_type": "branch",
                    "head": "18.0",
                    "url_protocol": "https",
                }
            )
        self.source.git_project_id = project
        backup = self.source.create_backup(self.backup_template)
        self.assertEqual(
            set(backup.git_project_data), {"sources", "git_aggregator_root_dir", "note"}
        )
        self.assertEqual(len(backup.git_project_data["sources"]), 1)
        self.restore_plan.line_ids.command_id.code = (
            "result = {'exit_code': 0 if "
            "jet.git_project_id.git_aggregator_root_dir == '/srv/git' "
            "and jet.git_project_id.note == 'Backup Git note' else 91}"
        )
        jet = backup.restore(self.server_test_1)
        self.assertNotEqual(jet.git_project_id, project)
        self.assertEqual(len(jet.git_project_id.source_ids), 1)
        self.assertFalse(jet.git_project_id.source_ids.enabled)
        self.assertEqual(len(jet.git_project_id.source_ids.remote_ids), 2)
        self.assertEqual(
            backup.plan_log_ids.filtered(
                lambda log: log.backup_operation == "restore"
            ).plan_status,
            0,
        )
        self.assertEqual(project.source_ids, source)
        self.assertNotEqual(jet.git_project_id.source_ids.reference, source.reference)
        self.source.git_project_id = False
        project.unlink()
        second = backup.restore(self.server_test_1)
        self.assertTrue(second.git_project_id)
        self.template.use_git_projects = False
        self.assertFalse(backup.restore(self.server_test_1).git_project_id)

    def test_no_git_project_without_remotes(self):
        self.template.use_git_projects = True
        backup = self._backup(
            git_project_data={"sources": [{"name": "Empty", "remotes": []}]}
        )
        self.assertFalse(backup.restore(self.server_test_1).git_project_id)
