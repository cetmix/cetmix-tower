# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from odoo.addons.cetmix_tower_server.tests.common import TestTowerCommon


class TestTowerTerminalCommon(TestTowerCommon):
    """Common base class for Cetmix Tower Terminal tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.TerminalSession = cls.env["cx.tower.terminal.session"]

    def _create_open_session(self, server=None, jet=None):
        """Create an open terminal session bound to the given server."""
        server = server or self.server_test_1
        vals = {
            "name": f"Terminal: {server.name}",
            "server_id": server.id,
        }
        if jet:
            vals["jet_id"] = jet.id
        return self.TerminalSession.create(vals)

    def _patch_broker_call(self, return_value=None):
        """Return a context manager that patches _broker_call on TerminalSession."""
        if return_value is None:
            return_value = {
                "status": "ok",
                "state": "open",
                "output": "",
                "message": False,
            }
        return patch(
            "odoo.addons.cetmix_tower_server_terminal.models."
            "cx_tower_terminal_session.CxTowerTerminalSession._broker_call",
            autospec=True,
            return_value=return_value,
        )

    def _patch_start_pusher(self):
        """Return a context manager that patches _start_output_pusher."""
        return patch(
            "odoo.addons.cetmix_tower_server_terminal.models."
            "cx_tower_terminal_session.CxTowerTerminalSession._start_output_pusher",
            autospec=True,
            return_value=None,
        )

    def _patch_stop_pusher(self):
        """Return a context manager that patches _stop_output_pusher."""
        return patch(
            "odoo.addons.cetmix_tower_server_terminal.models."
            "cx_tower_terminal_session.CxTowerTerminalSession._stop_output_pusher",
            autospec=True,
            return_value=None,
        )
