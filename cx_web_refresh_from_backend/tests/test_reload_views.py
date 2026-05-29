# Copyright 2025 Cetmix OÜ
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.base.tests.common import BaseCommon


@tagged("post_install", "-at_install")
class TestReloadViews(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_admin = cls.env.ref("base.user_admin")
        cls.user_demo = cls.env["res.users"].create(
            {
                "name": "Test User",
                "login": "test_refresh_user",
                "email": "test_refresh@example.com",
            }
        )

    def test_reload_views_basic(self):
        """Test basic reload_views call without parameters"""
        with patch.object(type(self.env["bus.bus"]), "_sendone") as mock_sendone:
            self.user_admin.reload_views(model="res.partner")

            mock_sendone.assert_called_once()
            partner, channel, message = mock_sendone.call_args[0]
            self.assertEqual(partner, self.user_admin.partner_id)
            self.assertEqual(channel, "web.refresh_view")
            self.assertEqual(message["model"], "res.partner")
            self.assertEqual(message["view_types"], [])
            self.assertEqual(message["rec_ids"], [])

    def test_reload_views_with_params(self):
        """Test reload_views with view_types and rec_ids parameters"""
        with patch.object(type(self.env["bus.bus"]), "_sendone") as mock_sendone:
            self.user_admin.reload_views(
                model="res.partner",
                view_types=["form", "kanban"],
                rec_ids=[self.partner.id],
            )

            mock_sendone.assert_called_once()
            message = mock_sendone.call_args[0][2]
            self.assertEqual(message["view_types"], ["form", "kanban"])
            self.assertEqual(message["rec_ids"], [self.partner.id])

    def test_reload_views_recordset(self):
        """Test reload_views on a multi-record user recordset.

        Ensures that calling reload_views on a recordset sends one notification
        per user through _sendone.
        """
        users = self.user_admin | self.user_demo

        with patch.object(type(self.env["bus.bus"]), "_sendone") as mock_sendone:
            users.reload_views(model="res.partner")

            self.assertEqual(mock_sendone.call_count, 2)

            # Verify both users' partners are notified and payload is correct.
            notified_partners = set()
            for call in mock_sendone.call_args_list:
                partner, channel, message = call[0]
                notified_partners.add(partner)
                self.assertEqual(channel, "web.refresh_view")
                self.assertEqual(message["model"], "res.partner")
                self.assertEqual(message["view_types"], [])
                self.assertEqual(message["rec_ids"], [])
            self.assertEqual(len(notified_partners), 2)
            self.assertEqual(
                notified_partners,
                {self.user_admin.partner_id, self.user_demo.partner_id},
            )
