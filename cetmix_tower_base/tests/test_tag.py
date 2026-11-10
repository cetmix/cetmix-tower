# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from odoo.exceptions import ValidationError

from .common import TestTowerBaseCommon


class TestTowerTag(TestTowerBaseCommon):
    """Tag deletion checks that live in cetmix_tower_base."""

    def test_manager_deletes_unused_tag(self):
        """A manager can delete an unused tag they created."""
        tag = self.Tag.with_user(self.user_manager).create({"name": "Unused Tag"})
        tag.with_user(self.user_manager).unlink()
        self.assertFalse(tag.exists())

    def test_usage_fields_block_manager_delete(self):
        """A set usage field blocks manager deletion and is ignored for root/sudo."""
        tag = self.Tag.with_user(self.user_manager).create(
            {"name": "Used Tag", "color": 5}
        )
        with patch.object(type(tag), "_get_tag_usage_fields", return_value=["color"]):
            with self.assertRaises(ValidationError):
                tag.with_user(self.user_manager).unlink()

            tag.with_user(self.user_root).unlink()
        self.assertFalse(tag.exists())

        tag_sudo = self.Tag.with_user(self.user_manager).create(
            {"name": "Used Tag Sudo", "color": 5}
        )
        with patch.object(
            type(tag_sudo), "_get_tag_usage_fields", return_value=["color"]
        ):
            tag_sudo.with_user(self.user_manager).sudo().unlink()
        self.assertFalse(tag_sudo.exists())
