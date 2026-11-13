# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from xmlrpc.client import Fault

from odoo.tests import HttpCase, tagged
from odoo.tests.common import JsonRpcException, new_test_user
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestBackupRpc(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        new_test_user(
            cls.env,
            login="backup_rpc_root",
            password="backup_rpc_root",
            groups="base.group_user,cetmix_tower_base.group_root",
        )

    def test_restore_is_private(self):
        self.authenticate("backup_rpc_root", "backup_rpc_root")
        with (
            mute_logger("odoo.http"),
            self.assertRaisesRegex(JsonRpcException, "odoo.exceptions.AccessError"),
        ):
            self.make_jsonrpc_request(
                "/web/dataset/call_kw",
                {
                    "model": "cx.tower.backup",
                    "method": "restore",
                    "args": [[0], 0],
                    "kwargs": {},
                },
            )

    def test_create_backup_is_private(self):
        self.authenticate("backup_rpc_root", "backup_rpc_root")
        with (
            mute_logger("odoo.http"),
            self.assertRaisesRegex(JsonRpcException, "odoo.exceptions.AccessError"),
        ):
            self.make_jsonrpc_request(
                "/web/dataset/call_kw",
                {
                    "model": "cx.tower.jet",
                    "method": "create_backup",
                    "args": [[0], "unknown"],
                    "kwargs": {},
                },
            )

    def test_backup_methods_are_private_over_xmlrpc(self):
        user = self.env["res.users"].search([("login", "=", "backup_rpc_root")])
        for model, method, argument in (
            ("cx.tower.backup", "restore", 0),
            ("cx.tower.jet", "create_backup", "unknown"),
        ):
            with (
                self.subTest(method=method),
                mute_logger("odoo.http"),
                self.assertRaises(Fault) as error,
            ):
                self.xmlrpc_object.execute_kw(
                    self.env.cr.dbname,
                    user.id,
                    "backup_rpc_root",
                    model,
                    method,
                    [[0], argument],
                    {},
                )
            self.assertIn("Private methods", error.exception.faultString)
