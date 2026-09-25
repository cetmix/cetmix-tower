# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError

from .common import TestDroneCommon


class TestDroneAccess(TestDroneCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.job = cls.target.launch_drone(
            "test_skill",
            cls.target._test_drone_done,
            {},
        ).sudo()
        cls.env.cr.postcommit.clear()

    def test_user_and_manager_have_no_access(self):
        for user in (self.user_user, self.user_manager):
            for records in (self.skill, self.controller_1, self.job):
                records = records.with_user(user)
                with self.assertRaises(AccessError):
                    records.read(["display_name"])
                with self.assertRaises(AccessError):
                    records.write({})
                with self.assertRaises(AccessError):
                    records.browse().create({})
                with self.assertRaises(AccessError):
                    records.unlink()

    def test_root_access(self):
        controller = self.Controller.with_user(self.user_root).create(
            {
                "name": "Root Controller",
                "controller_url": "https://root.example.com",
                "skill_ids": [(6, 0, [self.skill.id])],
                "drone_api_key": "root-api",
            }
        )
        controller.write({"priority": 3})
        self.assertEqual(controller._get_secret_value("drone_api_key"), "root-api")
        self.assertTrue(controller.read(["drone_api_key", "payload_key"]))
        controller.unlink()

        skill = self.skill.with_user(self.user_root)
        skill.write({"name": "Renamed"})

        job = self.job.with_user(self.user_root)
        self.assertTrue(job.read(["nonce", "state"])[0]["nonce"])
        with self.assertRaises(AccessError):
            job.write({"state": "done"})
        with self.assertRaises(AccessError):
            self.Job.with_user(self.user_root).create(
                {
                    "skill_id": self.skill.id,
                    "controller_id": self.controller_1.id,
                    "nonce": "x",
                    "res_model": "res.partner",
                    "res_ids": [1],
                    "method_name": "unlink",
                    "user_id": self.user_root.id,
                }
            )
        job.unlink()

    def test_nobody_writes_callback_fields(self):
        job = self.job
        for user in (self.user_user, self.user_manager, self.user_root):
            with self.assertRaises(AccessError):
                job.with_user(user).write({"method_name": "unlink"})
        # Not even with sudo
        with self.assertRaises(AccessError):
            job.sudo().write({"method_name": "unlink"})

    def test_action_cancel_requires_root(self):
        for user in (self.user_user, self.user_manager):
            with self.assertRaises(AccessError):
                self.job.with_user(user).action_cancel()
        self.assertEqual(self.job.state, "pending")
        self.job.with_user(self.user_root).action_cancel()
        self.assertEqual(self.job.state, "cancelled")

    def test_consumer_cancel_as_non_root(self):
        self.job.with_user(self.user_manager)._cancel()
        self.assertEqual(self.job.state, "cancelled")

    def test_menu_visibility(self):
        menus = (
            self.env.ref("cetmix_tower_drone.menu_cx_tower_drone_root")
            | self.env.ref("cetmix_tower_drone.cx_tower_drone_controller_menu")
            | self.env.ref("cetmix_tower_drone.cx_tower_drone_skill_menu")
            | self.env.ref("cetmix_tower_drone.cx_tower_drone_job_menu")
        )
        for user in (self.user_user, self.user_manager):
            visible = self.env["ir.ui.menu"].with_user(user)._visible_menu_ids()
            self.assertFalse(set(menus.ids) & set(visible))
        visible = self.env["ir.ui.menu"].with_user(self.user_root)._visible_menu_ids()
        self.assertTrue(set(menus.ids) <= set(visible))
