# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError

from .common import CommonTest


class TestGitRepoLines(CommonTest):
    """Repo line API, grouping G1-G5 and ordering."""

    def test_grouping_g1_g2_g4_g5(self):
        project = self.GitProject.create({"name": "Grouping Project"})
        project.add_repo_lines(
            [
                self._repo_line(self.repo_cetmix_tower, head="18.0"),
                self._repo_line(self.repo_cetmix_tower, head="19.0"),
                self._repo_line(self.repo_oca_web, head="main"),
            ]
        )
        remotes = project._get_flat_remotes()
        self.assertEqual(len(project.source_ids), 2)
        first_source = remotes[0].source_id
        self.assertEqual(remotes[0].source_id, remotes[1].source_id)
        self.assertNotEqual(remotes[0].source_id, remotes[2].source_id)
        self.assertEqual(first_source.remote_ids[0].head, "18.0")
        self.assertEqual(first_source.remote_ids[1].head, "19.0")
        self.assertEqual(
            first_source.name,
            f"{self.repo_cetmix_tower.owner_id.name}/{self.repo_cetmix_tower.repo}",
        )
        oca_source = remotes[2].source_id
        self.assertEqual(
            oca_source.name,
            f"{self.repo_oca_web.owner_id.name}/{self.repo_oca_web.repo}",
        )
        self.assertNotIn("Empty Source", project.source_ids.mapped("name"))

        extra_source = self.GitSource.create(
            {
                "name": "Second Same Repo",
                "git_project_id": project.id,
                "sequence": 999,
            }
        )
        self.GitRemote.create(
            {
                "source_id": extra_source.id,
                "repo_id": self.repo_cetmix_tower.id,
                "head_type": "branch",
                "head": "extra",
            }
        )
        project.add_repo_lines([self._repo_line(self.repo_cetmix_tower, head="g2")])
        g2_remote = project._get_flat_remotes().filtered(lambda rec: rec.head == "g2")
        self.assertEqual(g2_remote.source_id, first_source)

        # G4: deleting the only remote of a source deletes the source
        project_g4 = self.GitProject.create({"name": "G4 Project"})
        project_g4.add_repo_lines(
            [
                self._repo_line(self.repo_cetmix_tower),
                self._repo_line(self.repo_oca_web),
            ]
        )
        oca_source = project_g4.source_ids.filtered(
            lambda source: self.repo_oca_web in source.remote_ids.repo_id
        )
        project_g4.set_repo_lines([self._repo_line(self.repo_cetmix_tower)])
        self.assertFalse(oca_source.exists())
        self.assertEqual(len(project_g4.source_ids), 1)

    def test_reordering(self):
        project = self.GitProject.create({"name": "Order Project"})
        project.add_repo_lines(
            [
                self._repo_line(self.repo_cetmix_tower, head="first"),
                self._repo_line(self.repo_oca_web, head="second"),
                self._repo_line(self.repo_cetmix_tower, head="third"),
            ]
        )
        lines = project.get_repo_lines()
        reversed_lines = list(reversed(lines))
        project.set_repo_lines(reversed_lines)
        new_lines = project.get_repo_lines()
        self.assertEqual(
            [line["remote_id"] for line in new_lines],
            [line["remote_id"] for line in reversed_lines],
        )
        sources = project.source_ids.sorted("sequence")
        self.assertEqual(sources[0].remote_ids[:1].head, new_lines[0]["head"])
        code = project._git_aggregator_prepare_record()
        keys = list(code)
        self.assertTrue(keys[0].endswith(sources[0].reference))

    def test_repo_resolution_and_errors(self):
        project = self.GitProject.create({"name": "Resolve Project"})
        project.add_repo_lines([self._repo_line(self.repo_cetmix_tower)])
        by_ref = project.get_repo_lines()
        project_b = self.GitProject.create({"name": "Resolve B"})
        self.assertTrue(
            project_b.add_repo_lines(
                [
                    {
                        "repo_reference": self.repo_cetmix_tower.reference,
                        "head_type": "branch",
                        "head": "ref-head",
                    }
                ]
            )
        )
        self.assertTrue(
            project_b.add_repo_lines(
                [
                    {
                        "repo_url": self.repo_oca_web.url,
                        "head_type": "branch",
                        "head": "url-head",
                    }
                ]
            )
        )
        unknown_url = "https://github.com/new-org/new-repo.git"
        self.assertTrue(
            project_b.add_repo_lines(
                [
                    {
                        "repo_url": unknown_url,
                        "head_type": "branch",
                        "head": "created",
                    }
                ]
            )
        )
        self.assertTrue(
            self.Repo.search(
                [
                    ("host", "=", "github.com"),
                    ("repo", "=", "new-repo"),
                ]
            )
        )

        with self.assertRaises(ValidationError) as err:
            project.add_repo_lines([{"head_type": "branch", "head": "main"}])
        self.assertIn("0", str(err.exception))
        with self.assertRaises(ValidationError):
            project.add_repo_lines(
                [{"repo_id": self.repo_cetmix_tower.id, "head": "x"}]
            )
        with self.assertRaises(ValidationError):
            project.add_repo_lines(
                [{"repo_id": self.repo_cetmix_tower.id, "head_type": "branch"}]
            )
        with self.assertRaises(ValidationError):
            project.add_repo_lines(
                [
                    {
                        "repo_id": self.repo_cetmix_tower.id,
                        "head_type": "branch",
                        "head": "x",
                        "unknown": 1,
                    }
                ]
            )
        with self.assertRaises(ValidationError):
            project.add_repo_lines(
                [
                    {
                        "repo_reference": "does_not_exist_ref",
                        "head_type": "branch",
                        "head": "x",
                    }
                ]
            )
        with self.assertRaises(ValidationError):
            project.add_repo_lines(
                [{"repo_url": "not-a-url", "head_type": "branch", "head": "x"}]
            )
        with self.assertRaises(ValidationError):
            project.add_repo_lines(
                [
                    {
                        "repo_id": self.repo_cetmix_tower.id,
                        "repo_url": self.repo_oca_web.url,
                        "head_type": "branch",
                        "head": "x",
                    }
                ]
            )
        self.assertTrue(
            project.add_repo_lines(
                [
                    {
                        "repo_id": self.repo_oca_web.id,
                        "head_type": "branch",
                        "head": "ignored-source",
                        "source": "should-be-ignored",
                    }
                ]
            )
        )
        self.assertTrue(by_ref)

    def test_get_set_round_trip(self):
        project = self.GitProject.create({"name": "Round Trip"})
        project.add_repo_lines(
            [
                self._repo_line(self.repo_cetmix_tower, head="a"),
                self._repo_line(self.repo_oca_web, head="b"),
            ]
        )
        lines = project.get_repo_lines()
        ids_before = [line["remote_id"] for line in lines]
        self.assertTrue(project.set_repo_lines(lines))
        self.assertEqual(
            [line["remote_id"] for line in project.get_repo_lines()], ids_before
        )

    def test_set_repo_lines_match_create_delete(self):
        project = self.GitProject.create({"name": "Set Match"})
        project.add_repo_lines(
            [
                self._repo_line(self.repo_cetmix_tower, head="keep"),
                self._repo_line(self.repo_oca_web, head="drop"),
            ]
        )
        keep = project._get_flat_remotes().filtered(lambda rec: rec.head == "keep")
        self.assertTrue(
            project.set_repo_lines(
                [
                    self._repo_line(
                        self.repo_cetmix_tower,
                        remote_id=keep.id,
                        head="keep",
                        url_protocol="ssh",
                    ),
                    self._repo_line(self.repo_odoo_enterprise, head="new"),
                ]
            )
        )
        remotes = project._get_flat_remotes()
        self.assertEqual(keep.exists() and keep.id, remotes[0].id)
        self.assertEqual(keep.url_protocol, "ssh")
        self.assertEqual(len(remotes), 2)
        self.assertFalse(remotes.filtered(lambda rec: rec.repo_id == self.repo_oca_web))

    def test_set_remote_id_moves_record_g3(self):
        project = self.GitProject.create({"name": "G3 Project"})
        project.add_repo_lines(
            [
                self._repo_line(self.repo_cetmix_tower, head="move-me"),
                self._repo_line(self.repo_oca_web, head="oca"),
            ]
        )
        extra = self.GitSource.create(
            {
                "name": "First OCA",
                "git_project_id": project.id,
                "sequence": 0,
            }
        )
        self.GitRemote.create(
            {
                "source_id": extra.id,
                "repo_id": self.repo_oca_web.id,
                "head_type": "branch",
                "head": "already",
            }
        )
        remote = project._get_flat_remotes().filtered(lambda rec: rec.head == "move-me")
        remote_id = remote.id
        project.set_repo_lines(
            [
                self._repo_line(
                    self.repo_oca_web,
                    remote_id=remote_id,
                    head="moved",
                )
            ]
            + [
                line
                for line in project.get_repo_lines()
                if line["remote_id"] != remote_id
            ]
        )
        moved = self.GitRemote.browse(remote_id)
        self.assertTrue(moved.exists())
        self.assertEqual(moved.repo_id, self.repo_oca_web)
        self.assertEqual(moved.source_id, extra)

    def test_g3_new_source_composes_name(self):
        project = self.GitProject.create({"name": "G3 New Source Name"})
        project.add_repo_lines([self._repo_line(self.repo_cetmix_tower)])
        remote = project._get_flat_remotes()
        project.set_repo_lines(
            [self._repo_line(self.repo_oca_web, remote_id=remote.id)]
        )
        moved = self.GitRemote.browse(remote.id)
        self.assertEqual(moved.repo_id, self.repo_oca_web)
        self.assertEqual(
            moved.source_id.name,
            f"{self.repo_oca_web.owner_id.name}/{self.repo_oca_web.repo}",
        )

    def test_remote_id_errors_and_protocol_match(self):
        project = self.GitProject.create({"name": "Match Protocol"})
        project.add_repo_lines(
            [
                self._repo_line(
                    self.repo_cetmix_tower, head="same", url_protocol="https"
                ),
                self._repo_line(
                    self.repo_cetmix_tower, head="same", url_protocol="ssh"
                ),
            ]
        )
        https_id, ssh_id = (line["remote_id"] for line in project.get_repo_lines())
        self.assertTrue(
            project.set_repo_lines(
                [
                    self._repo_line(
                        self.repo_cetmix_tower, head="same", url_protocol="https"
                    ),
                    self._repo_line(
                        self.repo_cetmix_tower, head="same", url_protocol="ssh"
                    ),
                ]
            )
        )
        self.assertEqual(
            [line["remote_id"] for line in project.get_repo_lines()],
            [https_id, ssh_id],
        )
        other = self.GitProject.create({"name": "Other For Remote"})
        other.add_repo_lines([self._repo_line(self.repo_oca_web)])
        other_id = other.get_repo_lines()[0]["remote_id"]
        with self.assertRaises(ValidationError):
            project.set_repo_lines(
                [self._repo_line(self.repo_oca_web, remote_id=other_id)]
            )
        with self.assertRaises(ValidationError):
            project.set_repo_lines(
                [
                    self._repo_line(
                        self.repo_cetmix_tower, remote_id=https_id, head="a"
                    ),
                    self._repo_line(
                        self.repo_cetmix_tower, remote_id=https_id, head="b"
                    ),
                ]
            )

    def test_jet_methods_create_project_and_never_none(self):
        jet = self.jet_template_sample.create_jet(self.server_test_1, name="API Jet")
        self.assertEqual(jet.get_git_repo_lines(), [])
        self.assertTrue(
            jet.add_git_repo_lines(
                [self._repo_line(self.repo_cetmix_tower, head="api")]
            )
        )
        self.assertEqual(jet.git_project_id.name, jet.name)
        self.assertIsNotNone(jet.get_git_repo_lines())
        self.assertTrue(jet.set_git_repo_lines([self._repo_line(self.repo_oca_web)]))
        self.assertEqual(jet.get_git_repo_lines()[0]["repo_id"], self.repo_oca_web.id)
        project = self.GitProject.create({"name": "None Check"})
        self.assertIsNotNone(project.get_repo_lines())
        self.assertIsNotNone(project.add_repo_lines([]))
        self.assertIsNotNone(project.set_repo_lines([]))

    def test_wizards_match_api(self):
        wizard = self.env["cx.tower.jet.create.wizard"].create(
            {
                "name_type": "m",
                "name": "Wizard Structure",
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
                            "head": "wiz",
                            "url_protocol": "https",
                        },
                    )
                ],
            }
        )
        jet = self.Jet.browse(wizard.action_confirm()["res_id"])
        other = self.jet_template_sample.create_jet(
            self.server_test_1,
            name="API Structure",
            git_repo_lines=[self._repo_line(self.repo_cetmix_tower, head="wiz")],
        )
        self.assertEqual(
            [
                (line["repo_id"], line["head"], line["url_protocol"])
                for line in jet.get_git_repo_lines()
            ],
            [
                (line["repo_id"], line["head"], line["url_protocol"])
                for line in other.get_git_repo_lines()
            ],
        )
        self.assertEqual(len(jet.git_project_id.source_ids), 1)
        self.assertEqual(len(other.git_project_id.source_ids), 1)
