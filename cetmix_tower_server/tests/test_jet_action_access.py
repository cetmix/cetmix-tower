# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError

from .common_jets import TestTowerJetsCommon


class TestTowerJetActionAccess(TestTowerJetsCommon):
    """
    Test access rules for Jet Action model (cx.tower.jet.action)
    """

    # ======================
    # Manager Read Access
    # ======================

    def test_manager_read_access_level_manager_or_less(self):
        """Manager: can read when template access_level <= Manager (2)"""
        template = self.JetTemplate.create(
            {
                "name": "Manager Level Template",
                "reference": "manager_level_template",
                "access_level": "2",
            }
        )
        action = self.JetAction.create(
            {
                "name": "Action R",
                "reference": "action_r",
                "jet_template_id": template.id,
                "state_from_id": self.state_running.id,
                "state_to_id": self.state_stopped.id,
                "state_transit_id": self.state_stopping.id,
            }
        )

        records = self.JetAction.with_user(self.manager).search(
            [("id", "=", action.id)]
        )
        self.assertEqual(
            len(records), 1, "Manager should read when template level <= Manager"
        )

    def test_manager_read_when_in_template_users(self):
        """
        Manager: can read when added to template Users
        even if access_level is Root (3)
        """
        template = self.JetTemplate.create(
            {
                "name": "Root Level Template (user granted)",
                "reference": "root_level_template_user",
                "access_level": "3",
                "user_ids": [(4, self.manager.id)],
            }
        )
        action = self.JetAction.create(
            {
                "name": "Action RU",
                "reference": "action_ru",
                "jet_template_id": template.id,
                "state_from_id": self.state_running.id,
                "state_to_id": self.state_stopped.id,
                "state_transit_id": self.state_stopping.id,
            }
        )

        records = self.JetAction.with_user(self.manager).search(
            [("id", "=", action.id)]
        )
        self.assertEqual(len(records), 1, "Manager should read when in template Users")

    def test_manager_read_when_in_template_managers(self):
        """
        Manager: can read when added to template Managers
        even if access_level is Root (3)
        """
        template = self.JetTemplate.create(
            {
                "name": "Root Level Template (manager)",
                "reference": "root_level_template_manager",
                "access_level": "3",
                "manager_ids": [(4, self.manager.id)],
            }
        )
        action = self.JetAction.create(
            {
                "name": "Action RM",
                "reference": "action_rm",
                "jet_template_id": template.id,
                "state_from_id": self.state_running.id,
                "state_to_id": self.state_stopped.id,
                "state_transit_id": self.state_stopping.id,
            }
        )

        records = self.JetAction.with_user(self.manager).search(
            [("id", "=", action.id)]
        )
        self.assertEqual(
            len(records), 1, "Manager should read when in template Managers"
        )

    # ======================
    # Manager Write/Create/Delete
    # ======================

    def test_manager_write_when_in_template_managers(self):
        """Manager: can write when in template Managers"""
        template = self.JetTemplate.create(
            {
                "name": "Template For Write",
                "reference": "template_for_write",
                "manager_ids": [(4, self.manager.id)],
            }
        )
        action = self.JetAction.create(
            {
                "name": "Action W",
                "reference": "action_w",
                "jet_template_id": template.id,
                "state_from_id": self.state_running.id,
                "state_to_id": self.state_stopped.id,
                "state_transit_id": self.state_stopping.id,
            }
        )

        # Write
        self.JetAction.with_user(self.manager).browse(action.id).write({"priority": 99})
        action.invalidate_recordset()
        self.assertEqual(
            action.priority, 99, "Manager should be able to write when in Managers"
        )

        # Create
        created = self.JetAction.with_user(self.manager).create(
            {
                "name": "Action W Created",
                "reference": "action_w_created",
                "jet_template_id": template.id,
                "state_from_id": self.state_stopped.id,
                "state_to_id": self.state_running.id,
                "state_transit_id": self.state_starting.id,
            }
        )
        self.assertTrue(created, "Manager should be able to create when in Managers")

        # Delete
        self.JetAction.with_user(self.manager).browse(created.id).unlink()
        after = self.JetAction.search([("id", "=", created.id)])
        self.assertEqual(
            len(after), 0, "Manager should be able to delete when in Managers"
        )

    def test_manager_write_forbidden_when_not_in_template_managers(self):
        """Manager: cannot write/create/delete if NOT in template Managers"""
        template = self.JetTemplate.create(
            {
                "name": "Template No Write",
                "reference": "template_no_write",
            }
        )
        action = self.JetAction.create(
            {
                "name": "Action NW",
                "reference": "action_nw",
                "jet_template_id": template.id,
                "state_from_id": self.state_running.id,
                "state_to_id": self.state_stopped.id,
                "state_transit_id": self.state_stopping.id,
            }
        )

        # Write forbidden
        with self.assertRaises(AccessError):
            self.JetAction.with_user(self.manager).browse(action.id).write(
                {"priority": 5}
            )

        # Create forbidden
        with self.assertRaises(AccessError):
            self.JetAction.with_user(self.manager).create(
                {
                    "name": "Action NW Created",
                    "reference": "action_nw_created",
                    "jet_template_id": template.id,
                    "state_from_id": self.state_stopped.id,
                    "state_to_id": self.state_running.id,
                    "state_transit_id": self.state_starting.id,
                }
            )

        # Delete forbidden
        with self.assertRaises(AccessError):
            self.JetAction.with_user(self.manager).browse(action.id).unlink()

    def test_manager_write_on_root_level_template_when_in_managers(self):
        """Manager: can write/create/delete on Root-level template when in Managers"""
        template = self.JetTemplate.create(
            {
                "name": "Root Level Template For Write",
                "reference": "root_level_template_for_write",
                "access_level": "3",
                "manager_ids": [(4, self.manager.id)],
            }
        )
        action = self.JetAction.create(
            {
                "name": "Action RW",
                "reference": "action_rw",
                "jet_template_id": template.id,
                "state_from_id": self.state_running.id,
                "state_to_id": self.state_stopped.id,
                "state_transit_id": self.state_stopping.id,
            }
        )

        # Write
        self.JetAction.with_user(self.manager).browse(action.id).write({"priority": 42})
        action.invalidate_recordset()
        self.assertEqual(
            action.priority,
            42,
            "Manager should write on Root-level template when in Managers",
        )

        # Create
        created = self.JetAction.with_user(self.manager).create(
            {
                "name": "Action RW Created",
                "reference": "action_rw_created",
                "jet_template_id": template.id,
                "state_from_id": self.state_stopped.id,
                "state_to_id": self.state_running.id,
                "state_transit_id": self.state_starting.id,
            }
        )
        self.assertTrue(
            created, "Manager should create on Root-level template when in Managers"
        )

        # Delete
        self.JetAction.with_user(self.manager).browse(created.id).unlink()
        after = self.JetAction.search([("id", "=", created.id)])
        self.assertEqual(
            len(after),
            0,
            "Manager should delete on Root-level template when in Managers",
        )

    # ======================
    # Root Access
    # ======================

    def test_root_full_access(self):
        """Root: full CRUD access for any record"""
        template = self.JetTemplate.with_user(self.root).create(
            {
                "name": "Root Template",
                "reference": "root_template",
                "access_level": "3",
            }
        )

        # Create
        action = self.JetAction.with_user(self.root).create(
            {
                "name": "Root Action",
                "reference": "root_action",
                "jet_template_id": template.id,
                "state_from_id": self.state_initial.id,
                "state_to_id": self.state_running.id,
                "state_transit_id": self.state_starting.id,
            }
        )

        # Read
        records = self.JetAction.with_user(self.root).search([("id", "=", action.id)])
        self.assertEqual(len(records), 1, "Root should read any record")

        # Write
        action.with_user(self.root).write({"priority": 7})
        action.invalidate_recordset()
        self.assertEqual(action.priority, 7, "Root should update any record")

        # Delete
        action.with_user(self.root).unlink()
        self.assertEqual(
            len(
                self.JetAction.with_user(self.root).search(
                    [("reference", "=", "root_action")]
                )
            ),
            0,
            "Root should delete any record",
        )
