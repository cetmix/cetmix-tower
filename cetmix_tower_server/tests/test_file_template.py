from odoo.exceptions import AccessError

from .common import TestTowerCommon


class TestCxTowerFileTemplateAccessRules(TestTowerCommon):
    def test_user_no_access(self):
        """
        Verify that a user in the User group has no access
        to any file template records.
        """
        # Create a file template record as admin.
        record = self.FileTemplate.create(
            {
                "name": "Template 1",
                "file_name": "template1.txt",
                "code": "Sample code",
                "server_dir": "/templates",
                "file_type": "text",
                "source": "tower",
            }
        )
        # As the user, search for the record – expect no records.
        with self.assertRaises(AccessError):
            self.FileTemplate.with_user(self.user).search([("id", "=", record.id)])

        # Attempting to create a record as a user should raise an AccessError.
        with self.assertRaises(AccessError):
            self.FileTemplate.with_user(self.user).create(
                {
                    "name": "Template 2",
                    "file_name": "user_template.txt",
                    "code": "User code",
                    "server_dir": "/templates",
                    "file_type": "text",
                    "source": "tower",
                }
            )

    def test_manager_read_access(self):
        """
        Verify that a manager can read file template records
        if he is not in user_ids or manager_ids.
        """
        # Create a record with the manager in manager_ids.
        rec1 = self.FileTemplate.create(
            {
                "name": "Template 1",
                "file_name": "template_manager.txt",
                "code": "Manager code",
                "server_dir": "/templates",
                "file_type": "text",
                "source": "tower",
                "manager_ids": [(6, 0, [self.manager.id])],
            }
        )
        # Create a record with the manager in user_ids.
        rec2 = self.FileTemplate.create(
            {
                "name": "Template 2",
                "file_name": "template_user.txt",
                "code": "User code",
                "server_dir": "/templates",
                "file_type": "text",
                "source": "tower",
                "user_ids": [(6, 0, [self.manager.id])],
            }
        )
        # Create a record that does not include the manager.
        rec3 = self.FileTemplate.create(
            {
                "name": "Template 3",
                "file_name": "template_none.txt",
                "code": "None code",
                "server_dir": "/templates",
                "file_type": "text",
                "source": "tower",
            }
        )
        recs = self.FileTemplate.with_user(self.manager).search([])
        self.assertIn(rec1, recs, "Manager should read records if in manager_ids.")
        self.assertIn(rec2, recs, "Manager should read records if in user_ids.")
        self.assertNotIn(
            rec3,
            recs,
            "Manager should not see records if not in user_ids or manager_ids.",
        )

    def test_manager_write_create_access(self):
        """
        Verify that a manager can write and create file template records
        only if he is in manager_ids.
        """
        # Create a record with manager_ids including the manager.
        rec = self.FileTemplate.create(
            {
                "name": "Template 1",
                "file_name": "template_for_update.txt",
                "code": "Initial code",
                "server_dir": "/templates",
                "file_type": "text",
                "source": "tower",
                "manager_ids": [(6, 0, [self.manager.id])],
            }
        )
        # Manager should be able to update the record.
        try:
            rec.with_user(self.manager).write({"file_name": "template_updated.txt"})
        except AccessError:
            self.fail(
                "Manager should be able to update the record when in manager_ids."
            )
        self.assertEqual(rec.with_user(self.manager).file_name, "template_updated.txt")

        # Manager should be able to create a record if included in manager_ids.
        rec2 = self.FileTemplate.with_user(self.manager).create(
            {
                "name": "Template 2",
                "file_name": "manager_created_template.txt",
                "code": "Manager created",
                "server_dir": "/templates",
                "file_type": "text",
                "source": "tower",
                "manager_ids": [(6, 0, [self.manager.id])],
            }
        )
        self.assertTrue(
            rec2,
            "Manager should be able to create a record when included in manager_ids.",
        )

        # Creating a record without including the manager should raise an AccessError.
        with self.assertRaises(AccessError):
            self.FileTemplate.with_user(self.manager).create(
                {
                    "name": "Template 3",
                    "file_name": "invalid_template.txt",
                    "code": "Invalid",
                    "server_dir": "/templates",
                    "file_type": "text",
                    "source": "tower",
                    "manager_ids": [(5, 0, 0)],
                }
            )

    def test_manager_unlink_access(self):
        """
        Verify that a manager can delete a file template record only if
        he is in manager_ids and is the creator.
        """
        # Scenario 1: Record created by the manager.
        rec = self.FileTemplate.with_user(self.manager).create(
            {
                "name": "Template 1",
                "file_name": "template_to_delete.txt",
                "code": "Code to delete",
                "server_dir": "/templates",
                "file_type": "text",
                "source": "tower",
                "manager_ids": [(6, 0, [self.manager.id])],
            }
        )
        try:
            rec.with_user(self.manager).unlink()
        except AccessError:
            self.fail(
                "Manager should be able to delete a record "
                "he created when in manager_ids."
            )
        # Scenario 2: Record created by admin (or another user)
        # even though manager_ids includes the manager.
        rec2 = self.FileTemplate.create(
            {
                "name": "Template 2",
                "file_name": "template_not_deletable.txt",
                "code": "Admin created code",
                "server_dir": "/templates",
                "file_type": "text",
                "source": "tower",
                "manager_ids": [(6, 0, [self.manager.id])],
            }
        )
        with self.assertRaises(AccessError):
            rec2.with_user(self.manager).unlink()

    def test_root_unrestricted_access(self):
        """
        Verify that a user in the Root group has unlimited access
        to all file template records.
        """
        # Create a file template record (with no particular restrictions).
        rec = self.FileTemplate.create(
            {
                "name": "Template 1",
                "file_name": "template_for_root.txt",
                "code": "Root code",
                "server_dir": "/templates",
                "file_type": "text",
                "source": "tower",
            }
        )
        # As the root user, the record should be visible.
        recs = self.FileTemplate.with_user(self.root).search([("id", "=", rec.id)])
        self.assertTrue(recs, "Root should see the record regardless of restrictions.")
        # Root should be able to update the record.
        try:
            rec.with_user(self.root).write({"file_name": "root_updated_template.txt"})
        except AccessError:
            self.fail("Root should be able to update the record without restrictions.")
        self.assertEqual(
            rec.with_user(self.root).file_name, "root_updated_template.txt"
        )
        # Root should be able to create a record.
        rec2 = self.FileTemplate.with_user(self.root).create(
            {
                "name": "Template 2",
                "file_name": "root_created_template.txt",
                "code": "Created by root",
                "server_dir": "/templates",
                "file_type": "text",
                "source": "tower",
            }
        )
        self.assertTrue(
            rec2, "Root should be able to create a record without restrictions."
        )
        # Root should be able to delete a record.
        rec2.with_user(self.root).unlink()
        recs_after = self.FileTemplate.with_user(self.root).search(
            [("id", "=", rec2.id)]
        )
        self.assertFalse(
            recs_after, "Root should be able to delete the record without restrictions."
        )
