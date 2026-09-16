# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import Form

from odoo.addons.cetmix_tower_server.tests.common_jets import TestTowerJetsCommon

from .common import CommonTest


class TestJetGitProject(CommonTest, TestTowerJetsCommon):
    """Creation, naming, wizards and orphan deletion for Jet Git Projects."""

    def _fill_git_line_form(self, line, repo, head="main", head_type="branch"):
        """Fill a Git repo line the way the Jet tab and wizards do.

        Args:
            line (Form): Sub-form of ``git_remote_ids`` or
                ``git_repo_line_ids``.
            repo (cx.tower.git.repo): Repository to set.
            head (str): Branch, PR or commit. Defaults to ``main``.
            head_type (str): ``branch``, ``pr`` or ``commit``.
        """
        line.repo_id = repo
        line.url_protocol = "https"
        line.head_type = head_type
        line.head = head

    def _git_remote_form_index(self, jet_form, repo):
        """Return the Jet tab index of the remote for ``repo``.

        Args:
            jet_form (Form): Open Jet form.
            repo (cx.tower.git.repo): Repository to find.

        Returns:
            int: Index in ``git_remote_ids``.
        """
        for index, vals in enumerate(jet_form.git_remote_ids._records):
            repo_id = vals.get("repo_id")
            if repo_id == repo.id:
                return index
            if isinstance(repo_id, list) and repo_id and repo_id[0] == repo.id:
                return index
        raise AssertionError(f"Repository {repo.name} is not in the Git Project tab")

    def _save_launch_wizard_form(
        self, name, add_repositories="no", git_project=None, repo_lines=None
    ):
        """Fill and save the Launch wizard as the UI does.

        Args:
            name (str): Jet name (manual name type).
            add_repositories (str): ``no``, ``existing`` or ``repos``.
            git_project (cx.tower.git.project, optional): Project for
                ``existing``.
            repo_lines (list, optional): ``(repo, head, head_type)``
                tuples for ``repos``.

        Returns:
            recordset: Saved ``cx.tower.jet.create.wizard``.
        """
        with Form(self.env["cx.tower.jet.create.wizard"]) as wizard_form:
            wizard_form.jet_template_id = self.jet_template_sample
            wizard_form.server_id = self.server_test_1
            wizard_form.state_id = self.state_running
            wizard_form.name_type = "m"
            wizard_form.name = name
            wizard_form.add_repositories = add_repositories
            if git_project:
                wizard_form.git_project_id = git_project
            for repo, head, head_type in repo_lines or []:
                with wizard_form.git_repo_line_ids.new() as line:
                    self._fill_git_line_form(line, repo, head=head, head_type=head_type)
        wizard = wizard_form.record
        # Git fields are inside invisible="not state_id". The sample
        # template has no path to ``state_running``, and the ORM launch
        # tests omit state for that reason.
        wizard.state_id = False
        return wizard

    def _save_clone_wizard_form(
        self, parent, name, git_project_mode="copy", git_project=None, repo_lines=None
    ):
        """Fill and save the Clone wizard as the UI does.

        ``jet_id`` is readonly on the form, so the wizard is created
        with the parent Jet first.

        Args:
            parent (cx.tower.jet): Jet being cloned.
            name (str): Clone name (manual name type).
            git_project_mode (str): Clone Git mode.
            git_project (cx.tower.git.project, optional): Project for
                ``select``.
            repo_lines (list, optional): ``(repo, head, head_type)``
                tuples for ``repos``.

        Returns:
            recordset: Saved ``cx.tower.jet.clone.wizard``.
        """
        wizard = self.env["cx.tower.jet.clone.wizard"].create(
            {
                "jet_id": parent.id,
                "state_id": self.state_running.id,
            }
        )
        with Form(wizard) as wizard_form:
            wizard_form.name_type = "m"
            wizard_form.name = name
            wizard_form.git_project_mode = git_project_mode
            if git_project:
                wizard_form.git_project_id = git_project
            for repo, head, head_type in repo_lines or []:
                with wizard_form.git_repo_line_ids.new() as line:
                    self._fill_git_line_form(line, repo, head=head, head_type=head_type)
        return wizard_form.record

    def test_launch_no_creates_jet_without_project(self):
        wizard = self.env["cx.tower.jet.create.wizard"].create(
            {
                "name_type": "m",
                "name": "Jet Without Git",
                "jet_template_id": self.jet_template_sample.id,
                "server_id": self.server_test_1.id,
                "add_repositories": "no",
                "git_project_id": self.git_project_1.id,
                "git_repo_line_ids": [
                    (
                        0,
                        0,
                        {
                            "repo_id": self.repo_cetmix_tower.id,
                            "head_type": "branch",
                            "head": "main",
                        },
                    )
                ],
            }
        )
        jet = self.Jet.browse(wizard.action_confirm()["res_id"])
        self.assertFalse(jet.git_project_id)

    def test_launch_no_creates_jet_without_project_form(self):
        wizard = self._save_launch_wizard_form("Jet Without Git Form")
        jet = self.Jet.browse(wizard.action_confirm()["res_id"])
        self.assertFalse(jet.git_project_id)

    def test_launch_existing_links_project(self):
        wizard = self.env["cx.tower.jet.create.wizard"].create(
            {
                "name_type": "m",
                "name": "Jet Existing Git",
                "jet_template_id": self.jet_template_sample.id,
                "server_id": self.server_test_1.id,
                "add_repositories": "existing",
                "git_project_id": self.git_project_1.id,
            }
        )
        jet = self.Jet.browse(wizard.action_confirm()["res_id"])
        self.assertEqual(jet.git_project_id, self.git_project_1)
        copies = self.GitProject.search([("name", "ilike", "Jet Existing Git")])
        self.assertFalse(copies - self.git_project_1)

    def test_launch_existing_links_project_form(self):
        wizard = self._save_launch_wizard_form(
            "Jet Existing Git Form",
            add_repositories="existing",
            git_project=self.git_project_1,
        )
        jet = self.Jet.browse(wizard.action_confirm()["res_id"])
        self.assertEqual(jet.git_project_id, self.git_project_1)
        copies = self.GitProject.search([("name", "ilike", "Jet Existing Git Form")])
        self.assertFalse(copies - self.git_project_1)

    def test_select_existing_project_keeps_remotes(self):
        """Selecting a project must not apply the empty tab as SET []."""
        jet = self.jet_template_sample.create_jet(
            self.server_test_1, name="Select Existing Project Jet"
        )
        remotes = self.git_project_1.source_ids.remote_ids
        self.assertTrue(remotes)
        remote_ids = remotes.ids
        jet.write(
            {
                "git_project_id": self.git_project_1.id,
                "git_remote_ids": [(6, 0, [])],
            }
        )
        self.assertEqual(jet.git_project_id, self.git_project_1)
        self.assertEqual(
            set(self.git_project_1.source_ids.remote_ids.ids), set(remote_ids)
        )

    def test_select_existing_project_keeps_remotes_form(self):
        """Selecting a project in the Jet form must keep its remotes."""
        jet = self.jet_template_sample.create_jet(
            self.server_test_1, name="Select Existing Project Form Jet"
        )
        remotes = self.git_project_1.source_ids.remote_ids
        self.assertTrue(remotes)
        remote_ids = set(remotes.ids)
        with Form(jet) as jet_form:
            jet_form.git_project_id = self.git_project_1
        self.assertEqual(jet.git_project_id, self.git_project_1)
        self.assertEqual(set(self.git_project_1.source_ids.remote_ids.ids), remote_ids)

    def test_select_existing_project_still_adds_new_line(self):
        """CREATE commands on the same save as a project change still apply."""
        project = self.GitProject.create({"name": "Link And Add Project"})
        source = self.GitSource.create(
            {"name": "Existing Source", "git_project_id": project.id}
        )
        self.GitRemote.create(
            {
                "repo_id": self.repo_cetmix_tower.id,
                "source_id": source.id,
                "head_type": "branch",
                "head": "main",
            }
        )
        jet = self.jet_template_sample.create_jet(
            self.server_test_1, name="Select Project Add Line Jet"
        )
        jet.write(
            {
                "git_project_id": project.id,
                "git_remote_ids": [
                    (6, 0, []),
                    (
                        0,
                        0,
                        {
                            "repo_id": self.repo_odoo_enterprise.id,
                            "url_protocol": "https",
                            "head_type": "branch",
                            "head": "main",
                            "enabled": True,
                        },
                    ),
                ],
            }
        )
        self.assertEqual(len(project.source_ids.remote_ids), 2)
        self.assertIn(
            self.repo_odoo_enterprise,
            project.source_ids.remote_ids.repo_id,
        )

    def test_select_existing_project_still_adds_new_line_form(self):
        """CREATE from the Jet tab still applies with a project change."""
        project = self.GitProject.create({"name": "Link And Add Form Project"})
        source = self.GitSource.create(
            {"name": "Existing Source Form", "git_project_id": project.id}
        )
        self.GitRemote.create(
            {
                "repo_id": self.repo_cetmix_tower.id,
                "source_id": source.id,
                "head_type": "branch",
                "head": "main",
            }
        )
        jet = self.jet_template_sample.create_jet(
            self.server_test_1, name="Select Project Add Line Form Jet"
        )
        with Form(jet) as jet_form:
            jet_form.git_project_id = project
            with jet_form.git_remote_ids.new() as line:
                self._fill_git_line_form(line, self.repo_odoo_enterprise)
        self.assertEqual(len(project.source_ids.remote_ids), 2)
        self.assertIn(
            self.repo_odoo_enterprise,
            project.source_ids.remote_ids.repo_id,
        )

    def test_launch_select_repos_creates_named_project(self):
        wizard = self.env["cx.tower.jet.create.wizard"].create(
            {
                "name_type": "m",
                "name": "Unique Git Jet Name",
                "jet_template_id": self.jet_template_sample.id,
                "server_id": self.server_test_1.id,
                "add_repositories": "repos",
                "git_repo_line_ids": [
                    (
                        0,
                        0,
                        {
                            "repo_id": self.repo_cetmix_tower.id,
                            "head_type": "branch",
                            "head": "18.0",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "repo_id": self.repo_cetmix_tower.id,
                            "head_type": "pr",
                            "head": "12",
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "repo_id": self.repo_oca_web.id,
                            "head_type": "branch",
                            "head": "main",
                        },
                    ),
                ],
            }
        )
        jet = self.Jet.browse(wizard.action_confirm()["res_id"])
        self.assertEqual(jet.git_project_id.name, jet.name)
        self.assertEqual(jet.git_project_id.name, "Unique Git Jet Name")
        lines = jet.get_git_repo_lines()
        self.assertEqual(len(lines), 3)
        sources = jet.git_project_id.source_ids
        self.assertEqual(len(sources), 2)
        first_source = jet.git_project_id._get_flat_remotes()[0].source_id
        self.assertEqual(len(first_source.remote_ids), 2)
        self.assertEqual(first_source.remote_ids[0].repo_id, self.repo_cetmix_tower)

    def test_launch_select_repos_creates_named_project_form(self):
        wizard = self._save_launch_wizard_form(
            "Unique Git Jet Form Name",
            add_repositories="repos",
            repo_lines=[
                (self.repo_cetmix_tower, "18.0", "branch"),
                (self.repo_cetmix_tower, "12", "pr"),
                (self.repo_oca_web, "main", "branch"),
            ],
        )
        jet = self.Jet.browse(wizard.action_confirm()["res_id"])
        self.assertEqual(jet.git_project_id.name, jet.name)
        self.assertEqual(len(jet.get_git_repo_lines()), 3)
        self.assertEqual(len(jet.git_project_id.source_ids), 2)

    def test_launch_select_repos_no_lines_raises(self):
        wizard = self.env["cx.tower.jet.create.wizard"].create(
            {
                "name_type": "m",
                "name": "Empty Repos Jet",
                "jet_template_id": self.jet_template_sample.id,
                "server_id": self.server_test_1.id,
                "add_repositories": "repos",
            }
        )
        with self.assertRaises(ValidationError):
            wizard.action_confirm()

    def test_launch_select_repos_no_lines_raises_form(self):
        wizard = self._save_launch_wizard_form(
            "Empty Repos Form Jet", add_repositories="repos"
        )
        with self.assertRaises(ValidationError):
            wizard.action_confirm()

    def test_launch_select_repos_replaced_name(self):
        existing = self.jet_template_sample.create_jet(
            self.server_test_1, name="Taken Jet Name"
        )
        wizard = self.env["cx.tower.jet.create.wizard"].create(
            {
                "name_type": "m",
                "name": existing.name,
                "jet_template_id": self.jet_template_sample.id,
                "server_id": self.server_test_1.id,
                "add_repositories": "repos",
                "git_repo_line_ids": [
                    (
                        0,
                        0,
                        {
                            "repo_id": self.repo_cetmix_tower.id,
                            "head_type": "branch",
                            "head": "main",
                        },
                    )
                ],
            }
        )
        jet = self.Jet.browse(wizard.action_confirm()["res_id"])
        self.assertNotEqual(jet.name, existing.name)
        self.assertEqual(jet.git_project_id.name, jet.name)

    def test_allow_jet_creation_false_creates_no_project(self):
        count_before = self.GitProject.search_count([])
        with patch.object(
            type(self.jet_template_sample),
            "_allow_jet_creation",
            return_value=False,
        ):
            result = self.jet_template_sample.create_jet(
                self.server_test_1,
                name="Blocked Git Jet",
                git_repo_lines=[self._repo_line(self.repo_cetmix_tower)],
            )
        self.assertFalse(result)
        self.assertEqual(self.GitProject.search_count([]), count_before)

    def test_rename_unshared_project_keeps_reference(self):
        jet = self.jet_template_sample.create_jet(
            self.server_test_1,
            name="Rename Me Jet",
            git_repo_lines=[self._repo_line(self.repo_cetmix_tower)],
        )
        project = jet.git_project_id
        reference = project.reference
        jet.write({"name": "Renamed Jet"})
        self.assertEqual(project.name, "Renamed Jet")
        self.assertEqual(project.reference, reference)

    def test_rename_shared_project_keeps_name_and_reference(self):
        jet = self.jet_template_sample.create_jet(
            self.server_test_1,
            name="Shared Rename Jet",
            git_repo_lines=[self._repo_line(self.repo_cetmix_tower)],
        )
        other = self.jet_template_sample.create_jet(
            self.server_test_1,
            name="Other Shared Jet",
            git_project=jet.git_project_id.id,
        )
        project = jet.git_project_id
        reference = project.reference
        name = project.name
        jet.write({"name": "Renamed Shared Jet"})
        self.assertEqual(project.name, name)
        self.assertEqual(project.reference, reference)
        self.assertEqual(other.git_project_id, project)

    def test_rename_skips_when_archived_jet_uses_project(self):
        jet = self.jet_template_sample.create_jet(
            self.server_test_1,
            name="Active Rename Jet",
            git_repo_lines=[self._repo_line(self.repo_cetmix_tower)],
        )
        other = self.jet_template_sample.create_jet(
            self.server_test_1,
            name="Archived Shared Jet",
            git_project=jet.git_project_id.id,
        )
        project = jet.git_project_id
        name = project.name
        other.active = False
        jet.write({"name": "Should Not Rename Project"})
        self.assertEqual(project.name, name)

    def test_tab_new_line_creates_project(self):
        jet = self.jet_template_sample.create_jet(
            self.server_test_1, name="Tab Empty Jet"
        )
        self.assertFalse(jet.git_project_id)
        jet.write(
            {
                "git_remote_ids": [
                    (
                        0,
                        0,
                        {
                            "repo_id": self.repo_cetmix_tower.id,
                            "url_protocol": "https",
                            "head_type": "branch",
                            "head": "main",
                            "enabled": True,
                        },
                    )
                ]
            }
        )
        self.assertTrue(jet.git_project_id)
        self.assertEqual(jet.git_project_id.name, jet.name)
        remotes = jet.git_project_id._get_flat_remotes()
        self.assertEqual(len(remotes), 1)
        self.assertEqual(remotes.repo_id, self.repo_cetmix_tower)
        self.assertTrue(remotes.source_id)

    def test_tab_new_line_creates_project_form(self):
        jet = self.jet_template_sample.create_jet(
            self.server_test_1, name="Tab Empty Form Jet"
        )
        self.assertFalse(jet.git_project_id)
        with Form(jet) as jet_form:
            with jet_form.git_remote_ids.new() as line:
                self._fill_git_line_form(line, self.repo_cetmix_tower)
        self.assertTrue(jet.git_project_id)
        self.assertEqual(jet.git_project_id.name, jet.name)
        remotes = jet.git_project_id._get_flat_remotes()
        self.assertEqual(len(remotes), 1)
        self.assertEqual(remotes.repo_id, self.repo_cetmix_tower)

    def test_tab_new_line_groups_into_existing_source(self):
        jet = self._create_jet_with_project("Tab G1 Jet")
        self.assertEqual(len(jet.git_project_id.source_ids), 1)
        jet.write(
            {
                "git_remote_ids": [
                    (
                        0,
                        0,
                        {
                            "repo_id": self.repo_cetmix_tower.id,
                            "url_protocol": "https",
                            "head_type": "branch",
                            "head": "18.0",
                            "enabled": True,
                        },
                    )
                ]
            }
        )
        self.assertEqual(len(jet.git_project_id.source_ids), 1)
        self.assertEqual(len(jet.git_project_id.source_ids.remote_ids), 2)

    def test_tab_new_line_groups_into_existing_source_form(self):
        jet = self._create_jet_with_project("Tab G1 Form Jet")
        self.assertEqual(len(jet.git_project_id.source_ids), 1)
        with Form(jet) as jet_form:
            with jet_form.git_remote_ids.new() as line:
                self._fill_git_line_form(line, self.repo_cetmix_tower, head="18.0")
        self.assertEqual(len(jet.git_project_id.source_ids), 1)
        self.assertEqual(len(jet.git_project_id.source_ids.remote_ids), 2)

    def test_tab_change_repo_moves_remote(self):
        jet = self._create_jet_with_project(
            "Tab G3 Jet",
            lines=[
                self._repo_line(self.repo_cetmix_tower, head="main"),
                self._repo_line(self.repo_oca_web, head="main"),
            ],
        )
        remotes = jet.git_project_id._get_flat_remotes()
        tower_remote = remotes.filtered(
            lambda rec: rec.repo_id == self.repo_cetmix_tower
        )
        oca_source = remotes.filtered(
            lambda rec: rec.repo_id == self.repo_oca_web
        ).source_id
        old_source = tower_remote.source_id
        remote_id = tower_remote.id
        jet.write(
            {
                "git_remote_ids": [
                    (1, tower_remote.id, {"repo_id": self.repo_odoo_enterprise.id})
                ]
            }
        )
        moved = self.GitRemote.browse(remote_id)
        self.assertTrue(moved.exists())
        self.assertEqual(moved.repo_id, self.repo_odoo_enterprise)
        self.assertNotEqual(moved.source_id, old_source)
        self.assertFalse(old_source.exists())
        self.assertTrue(oca_source.exists())

    def test_tab_change_repo_moves_remote_form(self):
        jet = self._create_jet_with_project(
            "Tab G3 Form Jet",
            lines=[
                self._repo_line(self.repo_cetmix_tower, head="main"),
                self._repo_line(self.repo_oca_web, head="main"),
            ],
        )
        remotes = jet.git_project_id._get_flat_remotes()
        tower_remote = remotes.filtered(
            lambda rec: rec.repo_id == self.repo_cetmix_tower
        )
        oca_source = remotes.filtered(
            lambda rec: rec.repo_id == self.repo_oca_web
        ).source_id
        old_source = tower_remote.source_id
        remote_id = tower_remote.id
        with Form(jet) as jet_form:
            index = self._git_remote_form_index(jet_form, self.repo_cetmix_tower)
            with jet_form.git_remote_ids.edit(index) as line:
                line.repo_id = self.repo_odoo_enterprise
        moved = self.GitRemote.browse(remote_id)
        self.assertTrue(moved.exists())
        self.assertEqual(moved.repo_id, self.repo_odoo_enterprise)
        self.assertNotEqual(moved.source_id, old_source)
        self.assertFalse(old_source.exists())
        self.assertTrue(oca_source.exists())

    def test_tab_reorder_changes_source_order(self):
        jet = self._create_jet_with_project(
            "Tab Order Jet",
            lines=[
                self._repo_line(self.repo_cetmix_tower, head="first"),
                self._repo_line(self.repo_oca_web, head="second"),
            ],
        )
        remotes = jet.git_project_id._get_flat_remotes()
        first, second = remotes[0], remotes[1]
        self.assertEqual(first.repo_id, self.repo_cetmix_tower)
        jet.write(
            {
                "git_remote_ids": [
                    (1, first.id, {"sequence": 20}),
                    (1, second.id, {"sequence": 10}),
                ]
            }
        )
        new_remotes = jet.git_project_id._get_flat_remotes()
        self.assertEqual(new_remotes[0], second)
        self.assertEqual(new_remotes[1], first)
        sources = jet.git_project_id.source_ids.sorted("sequence")
        self.assertEqual(sources[0], second.source_id)
        self.assertEqual(sources[1], first.source_id)

    def test_tab_reorder_changes_source_order_form(self):
        jet = self._create_jet_with_project(
            "Tab Order Form Jet",
            lines=[
                self._repo_line(self.repo_cetmix_tower, head="first"),
                self._repo_line(self.repo_oca_web, head="second"),
            ],
        )
        remotes = jet.git_project_id._get_flat_remotes()
        first, second = remotes[0], remotes[1]
        with Form(jet) as jet_form:
            first_index = self._git_remote_form_index(jet_form, self.repo_cetmix_tower)
            second_index = self._git_remote_form_index(jet_form, self.repo_oca_web)
            with jet_form.git_remote_ids.edit(first_index) as line:
                line.sequence = 20
            with jet_form.git_remote_ids.edit(second_index) as line:
                line.sequence = 10
        new_remotes = jet.git_project_id._get_flat_remotes()
        self.assertEqual(new_remotes[0], second)
        self.assertEqual(new_remotes[1], first)

    def test_clone_copy_parent(self):
        self._enable_clone(self.jet_template_sample)
        parent = self.jet_template_sample.create_jet(
            self.server_test_1,
            name="Clone Parent",
            git_repo_lines=[self._repo_line(self.repo_cetmix_tower, head="18.0")],
        )
        wizard = self.env["cx.tower.jet.clone.wizard"].create(
            {
                "jet_id": parent.id,
                "name_type": "m",
                "name": "Clone Copy",
                "state_id": self.state_running.id,
                "git_project_mode": "copy",
            }
        )
        clone = self.Jet.browse(wizard.action_confirm()["res_id"])
        self.assertTrue(clone.git_project_id)
        self.assertNotEqual(clone.git_project_id, parent.git_project_id)
        self.assertEqual(clone.git_project_id.name, clone.name)
        self.assertNotIn("(copy)", clone.git_project_id.name)
        self.assertEqual(len(clone.get_git_repo_lines()), 1)

    def test_clone_copy_parent_form(self):
        self._enable_clone(self.jet_template_sample)
        parent = self.jet_template_sample.create_jet(
            self.server_test_1,
            name="Clone Parent Form",
            git_repo_lines=[self._repo_line(self.repo_cetmix_tower, head="18.0")],
        )
        wizard = self._save_clone_wizard_form(
            parent, "Clone Copy Form", git_project_mode="copy"
        )
        clone = self.Jet.browse(wizard.action_confirm()["res_id"])
        self.assertTrue(clone.git_project_id)
        self.assertNotEqual(clone.git_project_id, parent.git_project_id)
        self.assertEqual(clone.git_project_id.name, clone.name)
        self.assertEqual(len(clone.get_git_repo_lines()), 1)

    def test_clone_keep_parent(self):
        self._enable_clone(self.jet_template_sample)
        parent = self.jet_template_sample.create_jet(
            self.server_test_1,
            name="Keep Parent",
            git_repo_lines=[self._repo_line(self.repo_cetmix_tower)],
        )
        wizard = self.env["cx.tower.jet.clone.wizard"].create(
            {
                "jet_id": parent.id,
                "name_type": "m",
                "name": "Clone Keep",
                "state_id": self.state_running.id,
                "git_project_mode": "keep",
            }
        )
        clone = self.Jet.browse(wizard.action_confirm()["res_id"])
        self.assertEqual(clone.git_project_id, parent.git_project_id)

    def test_clone_keep_parent_form(self):
        self._enable_clone(self.jet_template_sample)
        parent = self.jet_template_sample.create_jet(
            self.server_test_1,
            name="Keep Parent Form",
            git_repo_lines=[self._repo_line(self.repo_cetmix_tower)],
        )
        wizard = self._save_clone_wizard_form(
            parent, "Clone Keep Form", git_project_mode="keep"
        )
        clone = self.Jet.browse(wizard.action_confirm()["res_id"])
        self.assertEqual(clone.git_project_id, parent.git_project_id)

    def test_clone_select_and_add_repos(self):
        self._enable_clone(self.jet_template_sample)
        parent = self.jet_template_sample.create_jet(
            self.server_test_1,
            name="Select Parent",
            git_repo_lines=[self._repo_line(self.repo_cetmix_tower)],
        )
        wizard = self.env["cx.tower.jet.clone.wizard"].create(
            {
                "jet_id": parent.id,
                "name_type": "m",
                "name": "Clone Select",
                "state_id": self.state_running.id,
                "git_project_mode": "select",
                "git_project_id": self.git_project_1.id,
            }
        )
        clone = self.Jet.browse(wizard.action_confirm()["res_id"])
        self.assertEqual(clone.git_project_id, self.git_project_1)

        wizard = self.env["cx.tower.jet.clone.wizard"].create(
            {
                "jet_id": parent.id,
                "name_type": "m",
                "name": "Clone Add Repos",
                "state_id": self.state_running.id,
                "git_project_mode": "repos",
                "git_repo_line_ids": [
                    (
                        0,
                        0,
                        {
                            "repo_id": self.repo_oca_web.id,
                            "head_type": "branch",
                            "head": "dev",
                        },
                    )
                ],
            }
        )
        clone = self.Jet.browse(wizard.action_confirm()["res_id"])
        self.assertEqual(clone.git_project_id.name, clone.name)
        self.assertEqual(clone.get_git_repo_lines()[0]["repo_id"], self.repo_oca_web.id)

    def test_clone_select_and_add_repos_form(self):
        self._enable_clone(self.jet_template_sample)
        parent = self.jet_template_sample.create_jet(
            self.server_test_1,
            name="Select Parent Form",
            git_repo_lines=[self._repo_line(self.repo_cetmix_tower)],
        )
        wizard = self._save_clone_wizard_form(
            parent,
            "Clone Select Form",
            git_project_mode="select",
            git_project=self.git_project_1,
        )
        clone = self.Jet.browse(wizard.action_confirm()["res_id"])
        self.assertEqual(clone.git_project_id, self.git_project_1)

        wizard = self._save_clone_wizard_form(
            parent,
            "Clone Add Repos Form",
            git_project_mode="repos",
            repo_lines=[(self.repo_oca_web, "dev", "branch")],
        )
        clone = self.Jet.browse(wizard.action_confirm()["res_id"])
        self.assertEqual(clone.git_project_id.name, clone.name)
        self.assertEqual(clone.get_git_repo_lines()[0]["repo_id"], self.repo_oca_web.id)

    def test_clone_parent_without_project(self):
        self._enable_clone(self.jet_template_sample)
        parent = self.jet_template_sample.create_jet(
            self.server_test_1, name="No Git Parent"
        )
        wizard = self.env["cx.tower.jet.clone.wizard"].create(
            {
                "jet_id": parent.id,
                "name_type": "m",
                "name": "Clone No Git",
                "state_id": self.state_running.id,
                "git_project_mode": "copy",
            }
        )
        clone = self.Jet.browse(wizard.action_confirm()["res_id"])
        self.assertFalse(clone.git_project_id)

    def test_clone_in_process_default_copies_parent(self):
        self._enable_clone(self.jet_template_sample)
        parent = self.jet_template_sample.create_jet(
            self.server_test_1,
            name="In Process Parent",
            git_repo_lines=[self._repo_line(self.repo_cetmix_tower)],
        )
        clone = parent.clone(name="In Process Clone")
        self.assertTrue(clone.git_project_id)
        self.assertNotEqual(clone.git_project_id, parent.git_project_id)
        self.assertEqual(clone.git_project_id.name, clone.name)

        parent_empty = self.jet_template_sample.create_jet(
            self.server_test_1, name="In Process Empty"
        )
        clone_empty = parent_empty.clone(name="In Process Empty Clone")
        self.assertFalse(clone_empty.git_project_id)

    def test_create_jet_two_git_kwargs_raise(self):
        with self.assertRaises(ValidationError):
            self.jet_template_sample.create_jet(
                self.server_test_1,
                name="Two Kwargs",
                git_project=self.git_project_1.id,
                git_repo_lines=[self._repo_line(self.repo_cetmix_tower)],
            )

    def test_relink_and_orphan(self):
        jet = self.jet_template_sample.create_jet(
            self.server_test_1,
            name="Relink Jet",
            git_repo_lines=[self._repo_line(self.repo_cetmix_tower)],
        )
        project = jet.git_project_id
        file = self.File.create(
            {
                "name": "repos.yml",
                "server_id": jet.server_id.id,
                "jet_id": jet.id,
                "source": "tower",
                "file_type": "text",
            }
        )
        self.GitProjectRel.create(
            {
                "git_project_id": project.id,
                "server_id": jet.server_id.id,
                "file_id": file.id,
                "project_format": project._default_project_format(),
            }
        )
        other = self.GitProject.create({"name": "Other Project"})
        jet.git_project_id = other
        self.assertEqual(file.git_project_rel_ids.git_project_id, other)

        already = self.GitProject.create({"name": "Already Linked"})
        self.GitProjectRel.create(
            {
                "git_project_id": already.id,
                "server_id": jet.server_id.id,
                "file_id": file.id,
                "project_format": already._default_project_format(),
            }
        )
        jet.git_project_id = already
        self.assertEqual(file.git_project_rel_ids.git_project_id, already)
        self.assertEqual(len(file.git_project_rel_ids), 1)

        jet.git_project_id = False
        self.assertEqual(file.git_project_rel_ids.git_project_id, already)
        self.assertTrue(file.exists())

        kept = self.jet_template_sample.create_jet(
            self.server_test_1,
            name="Kept By Other Jet",
            git_project=project.id,
        )
        jet2 = self.jet_template_sample.create_jet(
            self.server_test_1,
            name="To Delete Shared",
            git_project=project.id,
        )
        jet2.unlink()
        self.assertTrue(project.exists())

        keep_file = self.File.create(
            {
                "name": "keep.yml",
                "server_id": self.server_test_1.id,
                "source": "tower",
                "file_type": "text",
            }
        )
        self.GitProjectRel.create(
            {
                "git_project_id": project.id,
                "server_id": self.server_test_1.id,
                "file_id": keep_file.id,
                "project_format": project._default_project_format(),
            }
        )
        kept.unlink()
        self.assertTrue(project.exists())
        self.GitProjectRel.search([("git_project_id", "=", project.id)]).unlink()
        self.plan_line.create(
            {
                "plan_id": self.plan_1.id,
                "command_id": self.command_create_dir.id,
                "git_project_id": project.id,
            }
        )
        # Recreate a jet using the leftover project then delete it: plan line keeps it
        leftover_jet = self.jet_template_sample.create_jet(
            self.server_test_1,
            name="Plan Line Keeps Project",
            git_project=project.id,
        )
        leftover_jet.unlink()
        self.assertTrue(project.exists())

        only = self.jet_template_sample.create_jet(
            self.server_test_1,
            name="Only Jet Project",
            git_repo_lines=[self._repo_line(self.repo_oca_web)],
        )
        only_project = only.git_project_id
        only.unlink()
        self.assertFalse(only_project.exists())

        self.server_test_1.write(
            {
                "user_ids": [(4, self.manager.id)],
                "manager_ids": [(4, self.manager.id)],
            }
        )
        root_project = self.GitProject.create({"name": "Root Created Project"})
        root_project.write({"manager_ids": [(4, self.manager.id)]})
        manager_jet = self.jet_template_sample.with_user(self.manager).create_jet(
            self.server_test_1,
            name="Manager Orphan Jet",
            git_project=root_project.id,
        )
        manager_jet.with_user(self.manager).unlink()
        self.assertFalse(root_project.exists())
