# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.addons.cetmix_tower_server.tests.common_jets import TestTowerJetsCommon


class TestProjectTaskJet(TestTowerJetsCommon):
    """Project task and Jet link navigation."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user.write(
            {"groups_id": [(4, cls.env.ref("project.group_project_user").id)]}
        )
        cls.project = cls.env["project.project"].create(
            {
                "name": "Tower Project",
                "privacy_visibility": "employees",
            }
        )
        cls.task = cls.env["project.task"].create(
            {
                "name": "PR Task",
                "project_id": cls.project.id,
                "user_ids": [(4, cls.user.id)],
            }
        )
        cls.task_2 = cls.env["project.task"].create(
            {
                "name": "Other Task",
                "project_id": cls.project.id,
                "user_ids": [(4, cls.user.id)],
            }
        )

    def _link_jet(self, jet, task=None):
        """Add a Project task to ``task_ids`` without removing the others."""
        jet.write({"task_ids": [(4, (task or self.task).id)]})

    def _create_readable_jet(self, name, reference, **kwargs):
        """Create a Jet the Tower user can read.

        Args:
            name (str): Jet name.
            reference (str): Jet reference.
            **kwargs: Extra values forwarded to ``_create_jet``.

        Returns:
            cx.tower.jet: Created Jet.
        """
        kwargs.setdefault("user_ids", [(4, self.user.id)])
        kwargs.setdefault("server_user_ids", [(4, self.user.id)])
        return self._create_jet(name, reference, **kwargs)

    def test_task_ids_inverse(self):
        """Writing task_ids exposes the Jet on each task.jet_ids."""
        jet = self._create_readable_jet("Task Jet", "task_jet")
        self._link_jet(jet, self.task)
        self._link_jet(jet, self.task_2)
        self.assertIn(jet, self.task.jet_ids)
        self.assertIn(jet, self.task_2.jet_ids)
        self.assertEqual(jet.task_count, 2)

    def test_jet_count_zero(self):
        """Task with no linked Jets has jet_count 0."""
        self.assertEqual(self.task.jet_count, 0)

    def test_action_view_jets_single(self):
        """One visible Jet opens its form action."""
        jet = self._create_readable_jet("Single Jet", "single_jet")
        self._link_jet(jet)
        action = self.task.with_user(self.user).action_view_jets()
        self.assertEqual(action["res_model"], "cx.tower.jet")
        self.assertEqual(action["res_id"], jet.id)
        self.assertEqual(action["view_mode"], "form")
        self.assertFalse(action["context"].get("create"))

    def test_action_view_jets_multiple(self):
        """Several visible Jets open the base Jet action with a domain."""
        jet_a = self._create_readable_jet("Jet A", "jet_a")
        jet_b = self._create_readable_jet("Jet B", "jet_b")
        self._link_jet(jet_a)
        self._link_jet(jet_b)
        action = self.task.with_user(self.user).action_view_jets()
        self.assertEqual(action["res_model"], "cx.tower.jet")
        self.assertEqual(action["view_mode"], "kanban,list,form")
        self.assertEqual(action["views"][0][1], "kanban")
        self.assertEqual(action["domain"], [("id", "in", [jet_a.id, jet_b.id])])
        self.assertFalse(action["context"].get("create"))

    def test_jet_count_respects_jet_access(self):
        """A restricted user counts and opens only Jets they can read."""
        other_server = self.Server.create(
            {
                "name": "No Access Server",
                "ip_v4_address": "127.0.0.9",
                "ssh_username": "test",
                "ssh_password": "test",
            }
        )
        visible = self._create_readable_jet("Visible Jet", "visible_jet")
        hidden = self._create_jet(
            "Hidden Jet",
            "hidden_jet",
            server=other_server,
            user_ids=[(5, 0, 0)],
            server_user_ids=[(5, 0, 0)],
        )
        self._link_jet(visible)
        self._link_jet(hidden)
        self.assertEqual(self.task.jet_count, 2)
        self.env.invalidate_all()
        task_user = self.task.with_user(self.user)
        self.assertEqual(task_user.jet_count, 1)
        action = task_user.action_view_jets()
        self.assertEqual(action.get("res_id"), visible.id)
        self.assertEqual(action["view_mode"], "form")

    def test_jet_count_excludes_archived(self):
        """Archived Jets are not counted on the task."""
        jet = self._create_readable_jet("Archived Jet", "archived_jet")
        self._link_jet(jet)
        self.assertEqual(self.task.jet_count, 1)
        jet.active = False
        self.assertEqual(self.task.jet_count, 0)

    def test_archived_source_still_counts_with_active_test(self):
        """Archived source records keep their count when active_test is on."""
        jet = self._create_readable_jet("Source Jet", "source_jet")
        self._link_jet(jet, self.task)
        jet.active = False
        self.assertEqual(jet.task_count, 1)
        live_jet = self._create_readable_jet("Live Jet", "live_jet")
        self._link_jet(live_jet, self.task_2)
        self.task_2.active = False
        self.assertEqual(self.task_2.jet_count, 1)

    def test_copy_jet_clears_tasks(self):
        """Cloning a Jet does not copy task_ids."""
        jet = self._create_jet(
            "Copy Jet",
            "copy_jet",
            user_ids=[(4, self.manager.id)],
            manager_ids=[(4, self.manager.id)],
            server_user_ids=[(4, self.manager.id)],
            server_manager_ids=[(4, self.manager.id)],
        )
        self._link_jet(jet)
        clone = jet.copy({"name": "Copy Jet Clone"})
        self.assertFalse(clone.task_ids)

    def test_unlink_task_keeps_other_links(self):
        """Deleting one task drops only that link."""
        task = self.env["project.task"].create(
            {
                "name": "Delete Me",
                "project_id": self.project.id,
            }
        )
        jet = self._create_readable_jet("Unlink Jet", "unlink_jet")
        self._link_jet(jet, task)
        self._link_jet(jet, self.task_2)
        jet_id = jet.id
        task.unlink()
        jet = self.Jet.browse(jet_id)
        self.assertTrue(jet.exists())
        self.assertEqual(jet.task_ids, self.task_2)

    def test_action_view_tasks_single(self):
        """One visible task opens its form action."""
        jet = self._create_readable_jet("Task Form Jet", "task_form_jet")
        self._link_jet(jet, self.task)
        action = jet.with_user(self.user).action_view_tasks()
        self.assertEqual(action["res_model"], "project.task")
        self.assertEqual(action["res_id"], self.task.id)
        self.assertEqual(action["view_mode"], "form")
        self.assertFalse(action["context"].get("create"))
        self.assertNotIn("search_default_open_tasks", action["context"])

    def test_action_view_tasks_multiple(self):
        """Several visible tasks open the standard task action."""
        jet = self._create_readable_jet("Task List Jet", "task_list_jet")
        self._link_jet(jet, self.task)
        self._link_jet(jet, self.task_2)
        action = jet.with_user(self.user).action_view_tasks()
        self.assertEqual(action["res_model"], "project.task")
        self.assertIn("kanban", action["view_mode"].split(","))
        self.assertEqual(action["views"][0][1], "list")
        self.assertEqual(action["domain"][0][0], "id")
        self.assertEqual(set(action["domain"][0][2]), {self.task.id, self.task_2.id})
        self.assertFalse(action["context"].get("create"))
        self.assertNotIn("search_default_open_tasks", action["context"])

    def test_task_count_respects_task_access(self):
        """A restricted user counts and opens only tasks they can read."""
        private_project = self.env["project.project"].create(
            {
                "name": "Follower Project",
                "privacy_visibility": "followers",
            }
        )
        hidden_task = self.env["project.task"].create(
            {
                "name": "Hidden Task",
                "project_id": private_project.id,
                "user_ids": [(6, 0, [])],
            }
        )
        self.assertFalse(
            self.env["project.task"]
            .with_user(self.user)
            .search([("id", "=", hidden_task.id)])
        )
        jet = self._create_readable_jet("Access Jet", "access_task_jet")
        self._link_jet(jet, self.task)
        self._link_jet(jet, hidden_task)
        self.assertEqual(jet.task_count, 2)
        self.env.invalidate_all()
        jet_user = jet.with_user(self.user)
        self.assertEqual(jet_user.task_count, 1)
        action = jet_user.action_view_tasks()
        self.assertEqual(action.get("res_id"), self.task.id)
        self.assertEqual(action["view_mode"], "form")
