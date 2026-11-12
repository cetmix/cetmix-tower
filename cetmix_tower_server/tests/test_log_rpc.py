# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from unittest.mock import patch

from odoo.tests import HttpCase, tagged
from odoo.tests.common import JsonRpcException, new_test_user
from odoo.tools import mute_logger

from .common import TestTowerCommon


class TestLogExtensionHooks(TestTowerCommon):
    def test_python_extra_context_reaches_object_builder(self):
        command_type = type(self.Command)
        original = command_type._get_python_command_odoo_objects
        seen = []

        def objects(command, *args, **kwargs):
            seen.append(kwargs.get("extension_value"))
            return original(command, *args, **kwargs)

        with patch.object(command_type, "_get_python_command_odoo_objects", objects):
            result = self.server_test_1._run_python_code(
                "result = {'exit_code': 0}",
                extension_value="test-extension",
            )
        self.assertEqual(result["status"], 0)
        self.assertEqual(seen, ["test-extension"])


@tagged("post_install", "-at_install")
class TestLogRpc(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        new_test_user(
            cls.env,
            login="log_rpc_root",
            password="log_rpc_root",
            groups="base.group_user,cetmix_tower_base.group_root",
        )

    def test_log_lifecycle_methods_are_private(self):
        self.authenticate("log_rpc_root", "log_rpc_root")
        for model in ("cx.tower.plan.log", "cx.tower.command.log"):
            for method in ("start", "finish", "record"):
                with (
                    self.subTest(model=model, method=method),
                    mute_logger("odoo.http"),
                    self.assertRaisesRegex(
                        JsonRpcException, "odoo.exceptions.AccessError"
                    ),
                ):
                    self.make_jsonrpc_request(
                        "/web/dataset/call_kw",
                        {
                            "model": model,
                            "method": method,
                            "args": [[0]],
                            "kwargs": {},
                        },
                    )
            self.make_jsonrpc_request(
                "/web/dataset/call_kw",
                {
                    "model": model,
                    "method": "stop",
                    "args": [[]],
                    "kwargs": {},
                },
            )
