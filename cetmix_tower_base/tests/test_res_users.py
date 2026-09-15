# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from .common import TestTowerBaseCommon


class TestResUsers(TestTowerBaseCommon):
    """Access-level helper on res.users."""

    def test_cetmix_tower_access_level(self):
        """Return User/Manager/Root levels, or False without Tower groups."""
        # The helper reads env.user, not the record it is called on.
        self.assertEqual(
            self.Users.with_user(self.user_user)._cetmix_tower_access_level(),
            "1",
        )
        self.assertEqual(
            self.Users.with_user(self.user_manager)._cetmix_tower_access_level(),
            "2",
        )
        self.assertEqual(
            self.Users.with_user(self.user_root)._cetmix_tower_access_level(),
            "3",
        )
        self.assertFalse(
            self.Users.with_user(self.user_internal)._cetmix_tower_access_level()
        )
