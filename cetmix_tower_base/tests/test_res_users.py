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

    def test_role_domains_include_implied_groups(self):
        """Root remains selectable for roles inherited through implied groups."""
        roles = self.env["cx.tower.access.role.mixin"]
        for field_name in ("user_ids", "manager_ids"):
            domain = roles._fields[field_name].domain(roles)
            users = self.Users.search(domain)
            self.assertIn(self.user_root, users)
            self.assertIn(self.user_manager, users)
            self.assertNotIn(self.user_internal, users)
        self.assertIn(
            self.user_user, self.Users.search(roles._fields["user_ids"].domain(roles))
        )
        self.assertNotIn(
            self.user_user,
            self.Users.search(roles._fields["manager_ids"].domain(roles)),
        )
