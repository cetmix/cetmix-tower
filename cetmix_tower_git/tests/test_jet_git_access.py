# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError

from odoo.addons.cetmix_tower_server.tests.common_jets import TestTowerJetsCommon

from .common import CommonTest


class TestJetGitAccess(CommonTest, TestTowerJetsCommon):
    """Jet Git Project access (D12, D23) and wizard rights."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager_2 = cls.Users.create(
            {
                "name": "Second Git Manager",
                "login": "git_manager2",
                "email": "git_manager2@test.com",
                "groups_id": [(4, cls.group_manager.id)],
            }
        )

    def _grant_server_access(self, *users, managers=True):
        vals = {"user_ids": [(4, user.id) for user in users]}
        if managers:
            vals["manager_ids"] = [(4, user.id) for user in users]
        self.server_test_1.write(vals)

    def _grant_template_access(self, *users):
        self.jet_template_sample.write(
            {
                "user_ids": [(4, user.id) for user in users],
                "manager_ids": [(4, user.id) for user in users],
            }
        )

    def _set_jet_roles(self, jet, managers=(), users=()):
        jet.write(
            {
                "manager_ids": [(6, 0, [user.id for user in managers])],
                "user_ids": [(6, 0, [user.id for user in users])],
            }
        )

    def test_user_reads_via_jet(self):
        jet = self._create_jet_with_project("User Read Jet")
        project = jet.git_project_id
        source = project.source_ids[:1]
        remote = source.remote_ids[:1]
        owner = remote.repo_id.owner_id
        self._grant_server_access(self.user, managers=False)
        self._set_jet_roles(jet, users=(self.user,))

        user_project = project.with_user(self.user)
        self.assertEqual(user_project.name, jet.name)
        self.assertEqual(source.with_user(self.user).name, source.name)
        self.assertEqual(remote.with_user(self.user).head, remote.head)
        self.assertEqual(remote.repo_id.with_user(self.user).id, remote.repo_id.id)
        if owner:
            self.assertEqual(owner.with_user(self.user).id, owner.id)

        other = self._create_jet_with_project("No User Jet")
        with self.assertRaises(AccessError):
            other.git_project_id.with_user(self.user).read(["name"])

    def test_manager_shared_project_write(self):
        jet_a = self._create_jet_with_project("Shared A")
        project = jet_a.git_project_id
        jet_b = self.jet_template_sample.create_jet(
            self.server_test_1,
            name="Shared B",
            git_project=project.id,
        )
        self._grant_server_access(self.manager, self.manager_2)
        self._set_jet_roles(jet_a, managers=(self.manager,), users=(self.manager,))
        self._set_jet_roles(jet_b, managers=(self.manager_2,), users=(self.manager_2,))

        self.assertEqual(project.with_user(self.manager).name, jet_a.name)
        with self.assertRaises(AccessError):
            project.source_ids.with_user(self.manager).write({"name": "Nope"})
        with self.assertRaises(AccessError):
            project.source_ids.remote_ids.with_user(self.manager).write(
                {"head": "blocked"}
            )

        self._set_jet_roles(
            jet_b, managers=(self.manager, self.manager_2), users=(self.manager,)
        )
        project.source_ids.with_user(self.manager).write({"name": "Renamed Source"})
        self.assertEqual(project.source_ids[:1].name, "Renamed Source")

    def test_isolation_d23(self):
        jet = self._create_jet_with_project("Isolated Jet")
        project = jet.git_project_id
        file = self.File.create(
            {
                "name": "legacy.yml",
                "server_id": self.server_test_1.id,
                "source": "tower",
                "file_type": "text",
            }
        )
        rel = self.GitProjectRel.create(
            {
                "git_project_id": project.id,
                "server_id": self.server_test_1.id,
                "file_id": file.id,
                "project_format": project._default_project_format(),
            }
        )
        self._grant_server_access(self.manager)
        self._set_jet_roles(jet, managers=(self.manager_2,), users=(self.manager_2,))

        with self.assertRaises(AccessError):
            project.with_user(self.manager).read(["name"])
        with self.assertRaises(AccessError):
            project.source_ids.with_user(self.manager).read(["name"])
        with self.assertRaises(AccessError):
            rel.with_user(self.manager).read(["file_id"])

        self._set_jet_roles(jet, managers=(self.manager,), users=(self.manager,))
        self.assertEqual(project.with_user(self.manager).name, jet.name)
        self.assertTrue(project.source_ids.with_user(self.manager))
        self.assertEqual(rel.with_user(self.manager).file_id, file)

    def test_legacy_project_keeps_server_rules(self):
        project = self.GitProject.create({"name": "Legacy Only"})
        with self.assertRaises(AccessError):
            project.with_user(self.manager).read(["name"])
        project.write({"user_ids": [(4, self.manager.id)]})
        self.assertEqual(project.with_user(self.manager).name, "Legacy Only")
        with self.assertRaises(AccessError):
            project.with_user(self.manager).write({"name": "Nope"})
        project.write({"manager_ids": [(4, self.manager.id)]})
        project.with_user(self.manager).write({"name": "Legacy Updated"})
        self.assertEqual(project.name, "Legacy Updated")

    def test_manager_launch_and_clone(self):
        self._grant_server_access(self.manager)
        self._grant_template_access(self.manager)
        wizard = (
            self.env["cx.tower.jet.create.wizard"]
            .with_user(self.manager)
            .create(
                {
                    "name_type": "m",
                    "name": "Manager Launch Git",
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
        )
        jet = self.Jet.browse(wizard.action_confirm()["res_id"])
        self.assertEqual(jet.git_project_id.name, jet.name)

        self._enable_clone(self.jet_template_sample)
        clone_wizard = (
            self.env["cx.tower.jet.clone.wizard"]
            .with_user(self.manager)
            .create(
                {
                    "jet_id": jet.id,
                    "name_type": "m",
                    "name": "Manager Clone Git",
                    "state_id": self.state_running.id,
                    "git_project_mode": "copy",
                }
            )
        )
        clone = self.Jet.browse(clone_wizard.action_confirm()["res_id"])
        self.assertTrue(clone.git_project_id)
        self.assertNotEqual(clone.git_project_id, jet.git_project_id)
        self.assertEqual(clone.git_project_id.name, clone.name)

    def test_git_project_readonly(self):
        jet = self._create_jet_with_project("Readonly Jet")
        other = self.jet_template_sample.create_jet(
            self.server_test_1,
            name="Readonly Other",
            git_project=jet.git_project_id.id,
        )
        self._grant_server_access(self.user, self.manager, managers=True)
        self._set_jet_roles(
            jet, managers=(self.manager,), users=(self.user, self.manager)
        )
        self._set_jet_roles(other, managers=(self.manager_2,), users=(self.manager_2,))

        self.assertTrue(jet.with_user(self.user).git_project_readonly)
        self.assertTrue(jet.with_user(self.manager).git_project_readonly)

        self._set_jet_roles(
            other, managers=(self.manager, self.manager_2), users=(self.manager,)
        )
        manager_jet = jet.with_user(self.manager)
        self.assertFalse(
            manager_jet.git_project_readonly,
            manager_jet.git_project_readonly_reason,
        )

    def test_user_wizard_line_acl(self):
        Line = self.env["cx.tower.git.repo.line.wizard"]
        line = Line.with_user(self.user).create(
            {
                "repo_id": self.repo_cetmix_tower.id,
                "head_type": "branch",
                "head": "acl",
            }
        )
        line.with_user(self.user).write({"head": "acl-updated"})
        self.assertEqual(line.head, "acl-updated")
        line.with_user(self.user).unlink()
        self.assertFalse(line.exists())
        Line.with_user(self.manager).create(
            {
                "repo_id": self.repo_oca_web.id,
                "head_type": "branch",
                "head": "mgr",
            }
        )

    def test_cannot_attach_inaccessible_project(self):
        victim = self._create_jet_with_project("Victim Git")
        project = victim.git_project_id
        attacker = self.jet_template_sample.create_jet(
            self.server_test_1, name="Attacker Jet"
        )
        self._grant_server_access(self.manager_2)
        self._grant_template_access(self.manager_2)
        self._set_jet_roles(
            attacker, managers=(self.manager_2,), users=(self.manager_2,)
        )
        with self.assertRaises(AccessError):
            attacker.with_user(self.manager_2).write({"git_project_id": project.id})
        self.assertFalse(attacker.git_project_id)
        self.assertEqual(project.jet_ids, victim)
        with self.assertRaises(AccessError):
            self.jet_template_sample.with_user(self.manager_2).create_jet(
                self.server_test_1,
                name="Stolen Link Jet",
                git_project=project.id,
            )

    def test_archived_jet_keeps_jet_access_regime(self):
        jet = self._create_jet_with_project("Archive User Jet")
        project = jet.git_project_id
        self._grant_server_access(self.manager, self.manager_2)
        self._set_jet_roles(jet, managers=(self.manager,), users=(self.manager,))
        project.write({"user_ids": [(4, self.manager_2.id)]})
        jet.active = False
        self.assertEqual(project.with_user(self.manager).name, jet.name)
        with self.assertRaises(AccessError):
            project.with_user(self.manager_2).read(["name"])
