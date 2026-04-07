# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError

from .common_jets import TestTowerJetsCommon


class TestTowerJetActionAccess(TestTowerJetsCommon):
    """
    Test access rules for Jet Action model (cx.tower.jet.action)
    """

    # ======================
    # User Read Access
    # ======================

    def test_user_read_access_level_user_and_template_user(self):
        """
        User: can read when action access_level is User
        (1) AND template access_level is User (1)
        """
        template = self.JetTemplate.create(
            {
                "name": "User Level Template",
                "reference": "user_level_template",
                "access_level": "1",  # User level
                "user_ids": False,
                "manager_ids": False,
            }
        )
        action = self.JetAction.create(
            {
                "name": "Action U",
                "reference": "action_u",
                "access_level": "1",  # User level
                "jet_template_id": template.id,
                "state_from_id": self.state_running.id,
                "state_to_id": self.state_stopped.id,
                "state_transit_id": self.state_stopping.id,
            }
        )

        records = self.JetAction.with_user(self.user).search([("id", "=", action.id)])
        self.assertEqual(
            len(records),
            1,
            "User should read when action and template access_level are User",
        )

    def test_user_read_when_in_template_users(self):
        """
        User: can read when action access_level is User (1)
        AND user is added to template Users
        """
        template = self.JetTemplate.create(
            {
                "name": "Manager Level Template (user granted)",
                "reference": "manager_level_template_user",
                "access_level": "2",  # Manager level
                "user_ids": [(4, self.user.id)],
                "manager_ids": False,
            }
        )
        action = self.JetAction.create(
            {
                "name": "Action TU",
                "reference": "action_tu",
                "access_level": "1",  # User level
                "jet_template_id": template.id,
                "state_from_id": self.state_running.id,
                "state_to_id": self.state_stopped.id,
                "state_transit_id": self.state_stopping.id,
            }
        )

        records = self.JetAction.with_user(self.user).search([("id", "=", action.id)])
        self.assertEqual(
            len(records),
            1,
            "User should read when action access_level is"
            " User and user in template Users",
        )

    def test_user_read_when_in_jet_users(self):
        """
        User: can read when action access_level is
        User (1) AND user is added to Jet Users
        """
        template = self.JetTemplate.create(
            {
                "name": "Manager Level Template",
                "reference": "manager_level_template_jet",
                "access_level": "2",  # Manager level
                "user_ids": False,
                "manager_ids": False,
            }
        )
        # Add server to template's server_ids for jet creation
        template.write({"server_ids": [(4, self.server_test_1.id)]})
        self._create_jet(
            name="Test Jet from Template",
            reference="test_jet_from_template",
            template=template,
            server=self.server_test_1,
            user_ids=[(4, self.user.id)],  # Add user to Jet's user_ids
            server_user_ids=[(4, self.user.id)],  # Also add to server for jet access
        )
        action = self.JetAction.create(
            {
                "name": "Action JU",
                "reference": "action_ju",
                "access_level": "1",  # User level
                "jet_template_id": template.id,
                "state_from_id": self.state_running.id,
                "state_to_id": self.state_stopped.id,
                "state_transit_id": self.state_stopping.id,
            }
        )

        records = self.JetAction.with_user(self.user).search([("id", "=", action.id)])
        self.assertEqual(
            len(records),
            1,
            "User should read when action access_level is User and user in Jet Users",
        )

    def test_user_read_no_access_action_not_user_level(self):
        """User: cannot read when action access_level is NOT User (1)"""
        template = self.JetTemplate.create(
            {
                "name": "User Level Template",
                "reference": "user_level_template_no_access",
                "access_level": "1",  # User level
                "user_ids": False,
                "manager_ids": False,
            }
        )
        action = self.JetAction.create(
            {
                "name": "Action M",
                "reference": "action_m",
                "access_level": "2",  # Manager level
                "jet_template_id": template.id,
                "state_from_id": self.state_running.id,
                "state_to_id": self.state_stopped.id,
                "state_transit_id": self.state_stopping.id,
            }
        )

        records = self.JetAction.with_user(self.user).search([("id", "=", action.id)])
        self.assertEqual(
            len(records),
            0,
            "User should not read when action access_level is not User",
        )

    def test_user_read_no_access_template_conditions_not_met(self):
        """
        User: cannot read when action access_level is User (1)
        and template conditions not met
        """
        template = self.JetTemplate.create(
            {
                "name": "Manager Level Template",
                "reference": "manager_level_template_no_access",
                "access_level": "2",  # Manager level
                "user_ids": False,  # User not in template Users
                "manager_ids": False,
            }
        )
        # Don't create any jets with user in user_ids
        action = self.JetAction.create(
            {
                "name": "Action NA",
                "reference": "action_na",
                "access_level": "1",  # User level
                "jet_template_id": template.id,
                "state_from_id": self.state_running.id,
                "state_to_id": self.state_stopped.id,
                "state_transit_id": self.state_stopping.id,
            }
        )

        records = self.JetAction.with_user(self.user).search([("id", "=", action.id)])
        self.assertEqual(
            len(records),
            0,
            "User should not read when action is User level"
            " and template conditions not met",
        )

    def test_user_write_forbidden(self):
        """User: cannot write/create/delete records"""
        template = self.JetTemplate.create(
            {
                "name": "User Level Template",
                "reference": "user_level_template_write",
                "access_level": "1",
                "user_ids": [(4, self.user.id)],
            }
        )
        action = self.JetAction.create(
            {
                "name": "Action W",
                "reference": "action_w_user",
                "access_level": "1",
                "jet_template_id": template.id,
                "state_from_id": self.state_running.id,
                "state_to_id": self.state_stopped.id,
                "state_transit_id": self.state_stopping.id,
            }
        )

        # Write forbidden
        with self.assertRaises(AccessError):
            self.JetAction.with_user(self.user).browse(action.id).write({"priority": 5})

        # Create forbidden
        with self.assertRaises(AccessError):
            self.JetAction.with_user(self.user).create(
                {
                    "name": "Action Created",
                    "reference": "action_created_user",
                    "access_level": "1",
                    "jet_template_id": template.id,
                    "state_from_id": self.state_stopped.id,
                    "state_to_id": self.state_running.id,
                    "state_transit_id": self.state_starting.id,
                }
            )

        # Delete forbidden
        with self.assertRaises(AccessError):
            self.JetAction.with_user(self.user).browse(action.id).unlink()

    # ======================
    # Manager Read Access
    # ======================

    def test_manager_read_access_level_manager_or_less(self):
        """
        Manager: can read when action access_level <= Manager (2)
        AND template access_level <= Manager (2)
        """
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
                "access_level": "2",  # Manager level
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
            len(records),
            1,
            "Manager should read when action and template level <= Manager",
        )

    def test_manager_read_when_in_template_users(self):
        """
        Manager: can read when action access_level <= Manager (2)
        AND user is added to template Users
        even if template access_level is Root (3)
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
                "access_level": "2",  # Manager level
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
            len(records),
            1,
            "Manager should read when action level <= Manager and in template Users",
        )

    def test_manager_read_when_in_template_managers(self):
        """
        Manager: can read when action access_level <= Manager (2)
        AND user is added to template Managers
        even if template access_level is Root (3)
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
                "access_level": "2",  # Manager level
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
            len(records),
            1,
            "Manager should read when action level <= Manager and in template Managers",
        )

    def test_manager_read_no_access_action_root_level(self):
        """
        Manager: cannot read when action access_level is Root (3)
        even if template conditions are met
        """
        template = self.JetTemplate.create(
            {
                "name": "Manager Level Template",
                "reference": "manager_level_template_no_access",
                "access_level": "2",
                "manager_ids": [(4, self.manager.id)],
            }
        )
        action = self.JetAction.create(
            {
                "name": "Action Root",
                "reference": "action_root",
                "access_level": "3",  # Root level
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
            len(records),
            0,
            "Manager should not read when action access_level is Root",
        )

    # ======================
    # Manager Write/Create/Delete
    # ======================

    def test_manager_write_when_in_template_managers(self):
        """
        Manager: can write when action access_level <= Manager (2)
        AND user is in template Managers
        """
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
                "access_level": "2",  # Manager level
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
            action.priority,
            99,
            "Manager should be able to write when action level"
            " <= Manager and in Managers",
        )

        # Create
        created = self.JetAction.with_user(self.manager).create(
            {
                "name": "Action W Created",
                "reference": "action_w_created",
                "access_level": "2",  # Manager level
                "jet_template_id": template.id,
                "state_from_id": self.state_stopped.id,
                "state_to_id": self.state_running.id,
                "state_transit_id": self.state_starting.id,
            }
        )
        self.assertTrue(
            created,
            "Manager should be able to create when action level "
            "<= Manager and in Managers",
        )

        # Delete
        self.JetAction.with_user(self.manager).browse(created.id).unlink()
        after = self.JetAction.search([("id", "=", created.id)])
        self.assertEqual(
            len(after),
            0,
            "Manager should be able to delete when action level "
            "<= Manager and in Managers",
        )

    def test_manager_write_forbidden_when_not_in_template_managers(self):
        """
        Manager: cannot write/create/delete if NOT in template Managers
        even if action access_level <= Manager (2)
        """
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
                "access_level": "2",  # Manager level
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
                    "access_level": "2",  # Manager level
                    "jet_template_id": template.id,
                    "state_from_id": self.state_stopped.id,
                    "state_to_id": self.state_running.id,
                    "state_transit_id": self.state_starting.id,
                }
            )

        # Delete forbidden
        with self.assertRaises(AccessError):
            self.JetAction.with_user(self.manager).browse(action.id).unlink()

    def test_manager_write_forbidden_when_action_root_level(self):
        """
        Manager: cannot write/create/delete when action access_level is Root (3)
        even if user is in template Managers
        """
        template = self.JetTemplate.create(
            {
                "name": "Template For Write",
                "reference": "template_for_write_root",
                "manager_ids": [(4, self.manager.id)],
            }
        )
        action = self.JetAction.create(
            {
                "name": "Action Root W",
                "reference": "action_root_w",
                "access_level": "3",  # Root level
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
                    "name": "Action Root Created",
                    "reference": "action_root_created",
                    "access_level": "3",  # Root level
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
        """
        Manager: can write/create/delete on Root-level template
        when action access_level <= Manager (2) AND user is in Managers
        """
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
                "access_level": "2",  # Manager level
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
            "Manager should write on Root-level template when action level "
            "<= Manager and in Managers",
        )

        # Create
        created = self.JetAction.with_user(self.manager).create(
            {
                "name": "Action RW Created",
                "reference": "action_rw_created",
                "access_level": "2",  # Manager level
                "jet_template_id": template.id,
                "state_from_id": self.state_stopped.id,
                "state_to_id": self.state_running.id,
                "state_transit_id": self.state_starting.id,
            }
        )
        self.assertTrue(
            created,
            "Manager should create on Root-level template when action level "
            "<= Manager and in Managers",
        )

        # Delete
        self.JetAction.with_user(self.manager).browse(created.id).unlink()
        after = self.JetAction.search([("id", "=", created.id)])
        self.assertEqual(
            len(after),
            0,
            "Manager should delete on Root-level template when action level "
            "<= Manager and in Managers",
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
