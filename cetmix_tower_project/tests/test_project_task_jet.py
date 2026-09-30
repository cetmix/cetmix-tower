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
        """Set ``project_task_id`` on a Jet."""
        jet.write({"project_task_id": (task or self.task).id})

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

    def test_project_task_id_inverse(self):
        """Writing project_task_id exposes the Jet on task.jet_ids."""
        jet = self._create_readable_jet("Task Jet", "task_jet")
        self._link_jet(jet)
        self.assertIn(jet, self.task.jet_ids)

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
        """Several visible Jets open a list action with a domain."""
        jet_a = self._create_readable_jet("Jet A", "jet_a")
        jet_b = self._create_readable_jet("Jet B", "jet_b")
        self._link_jet(jet_a)
        self._link_jet(jet_b)
        action = self.task.with_user(self.user).action_view_jets()
        self.assertEqual(action["res_model"], "cx.tower.jet")
        self.assertEqual(action["view_mode"], "list,form")
        self.assertEqual(action["views"][0][1], "list")
        self.assertEqual(action["domain"], [("id", "in", [jet_a.id, jet_b.id])])
        self.assertFalse(action["context"].get("create"))

    def test_jet_count_respects_jet_access(self):
        """A cached superuser read is not reused for a restricted user."""
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
        task_user = self.task.with_user(self.user)
        self.assertEqual(task_user.jet_count, 1)
        # Warm the shared One2many cache before the restricted user acts.
        sudo_jets = self.task.sudo().jet_ids
        self.assertEqual(len(sudo_jets), 2)
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
        self.assertEqual(self.task.with_context(active_test=False).jet_count, 1)

    def test_copy_jet_clears_project_task(self):
        """Cloning a Jet does not copy project_task_id."""
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
        self.assertFalse(clone.project_task_id)

    def test_unlink_task_clears_jet_link(self):
        """Deleting the task clears project_task_id on the Jet."""
        task = self.env["project.task"].create(
            {
                "name": "Delete Me",
                "project_id": self.project.id,
            }
        )
        jet = self._create_readable_jet("Unlink Jet", "unlink_jet")
        jet.write({"project_task_id": task.id})
        jet_id = jet.id
        task.unlink()
        jet = self.Jet.browse(jet_id)
        self.assertFalse(jet.project_task_id)

    def test_move_jet_to_other_task(self):
        """Reassigning project_task_id moves the Jet between tasks."""
        jet = self._create_readable_jet("Move Jet", "move_jet")
        self._link_jet(jet, self.task)
        self.assertIn(jet, self.task.jet_ids)
        jet.write({"project_task_id": self.task_2.id})
        self.assertNotIn(jet, self.task.jet_ids)
        self.assertIn(jet, self.task_2.jet_ids)
