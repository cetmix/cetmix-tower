from odoo.exceptions import AccessError, ValidationError

from .common import TestTowerCommon


class TestTowerTag(TestTowerCommon):
    """Test for the 'cx.tower.tag' model"""

    def test_01_unlink_as_user_with_used_tag(self):
        """Test that user cannot delete tag that is in use"""
        # Create test tag
        test_tag = self.Tag.create(
            {
                "name": "Test Tag User",
            }
        )
        # Link tag to server
        self.server_test_1.write({"tag_ids": [(4, test_tag.id)]})

        with self.assertRaises(ValidationError):
            test_tag.with_user(self.user).unlink()

    def test_02_unlink_as_user_with_unused_tag(self):
        """Test that user cannot delete tag even if it's not in use"""
        # Create new unused tag
        unused_tag = self.Tag.create(
            {
                "name": "Unused Tag",
            }
        )
        # Try to delete unused tag
        with self.assertRaises(AccessError):
            unused_tag.with_user(self.user).unlink()

    def test_03_unlink_as_manager_with_used_tag(self):
        """Test that manager cannot delete tag that is in use"""
        # Create test tag as manager
        test_tag = self.Tag.with_user(self.manager).create(
            {
                "name": "Test Tag Manager",
            }
        )
        # Link tag to server
        test_tag.write({"server_ids": [(4, self.server_test_1.id)]})

        # Access error because user doesn't have access to server
        with self.assertRaises(AccessError):
            test_tag.with_user(self.user).unlink()

        # Add 'manager' to server
        self.server_test_1.write({"user_ids": [(4, self.manager.id)]})

        # Validation error
        with self.assertRaises(ValidationError):
            test_tag.with_user(self.manager).unlink()

    def test_04_unlink_as_manager_with_own_tag(self):
        """Test that manager can delete their own unused tag"""
        # Create new unused tag as manager
        unused_tag = self.Tag.with_user(self.manager).create(
            {
                "name": "Manager's Tag",
            }
        )
        # Manager should be able to delete their own unused tag
        unused_tag.with_user(self.manager).unlink()

    def test_05_unlink_as_manager_with_other_tag(self):
        """Test that manager cannot delete tag created by other user"""
        # Create tag as root
        other_tag = self.Tag.create(
            {
                "name": "Other's Tag",
            }
        )
        # Manager should not be able to delete tag created by other user
        with self.assertRaises(AccessError):
            other_tag.with_user(self.manager).unlink()

    def test_06_unlink_as_sudo(self):
        """Test that sudo can delete tag that is in use"""
        # Create test tag
        test_tag = self.Tag.create(
            {
                "name": "Test Tag Sudo",
            }
        )
        # Link tag to server
        self.server_test_1.write({"tag_ids": [(4, test_tag.id)]})

        test_tag.with_user(self.user).sudo().unlink()
