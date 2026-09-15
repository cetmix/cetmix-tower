# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.addons.base.tests.common import BaseCommon


class TestTowerBaseCommon(BaseCommon):
    """Common fixtures for cetmix_tower_base tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tower_group_user = cls.env.ref("cetmix_tower_base.group_user")
        cls.tower_group_manager = cls.env.ref("cetmix_tower_base.group_manager")
        cls.tower_group_root = cls.env.ref("cetmix_tower_base.group_root")

        cls.Users = cls.env["res.users"]
        cls.user_internal = cls.Users.create(
            {
                "name": "Tower Internal",
                "login": "tower_internal",
                "email": "tower_internal@example.com",
                "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )
        cls.user_user = cls.Users.create(
            {
                "name": "Tower User",
                "login": "tower_user",
                "email": "tower_user@example.com",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.tower_group_user.id,
                            cls.env.ref("base.group_user").id,
                        ],
                    )
                ],
            }
        )
        cls.user_manager = cls.Users.create(
            {
                "name": "Tower Manager",
                "login": "tower_manager",
                "email": "tower_manager@example.com",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.tower_group_manager.id,
                            cls.env.ref("base.group_user").id,
                        ],
                    )
                ],
            }
        )
        cls.user_root = cls.Users.create(
            {
                "name": "Tower Root",
                "login": "tower_root",
                "email": "tower_root@example.com",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            cls.tower_group_root.id,
                            cls.env.ref("base.group_user").id,
                        ],
                    )
                ],
            }
        )
        cls.Tag = cls.env["cx.tower.tag"]
