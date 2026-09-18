# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json
from unittest.mock import patch

from cryptography.fernet import Fernet

from odoo.addons.cetmix_tower_drone.tests.common import FakeDroneNetwork
from odoo.addons.cetmix_tower_server.tests.common import TestTowerCommon

from ..models.constants import NO_CONTROLLER_POLICY_PARAM, SKILL_SSH


class TestDroneSshCommon(TestTowerCommon):
    """Common fixtures for drone SSH tests.

    Only the drone defer handler is active, so that an installed queue
    module does not change the outcome. Tests that need the full handler
    list use `real_defer_handlers()`.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not cls.registry.in_test_mode():
            cls.registry.enter_test_mode(cls.cr)
            cls.addClassCleanup(cls.registry.leave_test_mode)

        cls.Job = cls.env["cx.tower.drone.job"]
        cls.Controller = cls.env["cx.tower.drone.controller"]

        # Defer handlers
        server_class = type(cls.Server)
        # Plain function, not bound to the test case
        cls.original_defer_handlers = staticmethod(
            server_class._get_command_defer_handlers
        )
        cls.startClassPatcher(
            patch.object(
                server_class,
                "_get_command_defer_handlers",
                lambda self: [(10, self._try_defer_command_drone)],
            )
        )

        # Outbound HTTP
        cls.network = FakeDroneNetwork()
        cls.startClassPatcher(
            patch("requests.request", side_effect=cls.network.request)
        )

        # Skill
        cls.skill_ssh = cls.env["cx.tower.drone.skill"].search(
            [("code", "=", SKILL_SSH)]
        ) or cls.env["cx.tower.drone.skill"].create({"name": "SSH", "code": SKILL_SSH})
        cls.controller_1 = cls._create_controller("SSH Controller 1", priority=1)
        cls.controller_2 = cls._create_controller("SSH Controller 2", priority=2)

        cls.ICP = cls.env["ir.config_parameter"].sudo()
        cls.ICP.set_param("web.base.url", "https://tower.example.com")
        cls.ICP.set_param("cetmix_tower_server.command_timeout", "600")
        cls.ICP.set_param(NO_CONTROLLER_POLICY_PARAM, "fail")

        cls.command_ssh = cls.Command.create(
            {"name": "Drone SSH", "action": "ssh_command", "code": "ls -la"}
        )

    @classmethod
    def _create_controller(cls, name, **vals):
        values = {
            "name": name,
            "controller_url": f"https://{name.lower().replace(' ', '-')}.example.com",
            "skill_ids": [(6, 0, cls.skill_ssh.ids)],
            "status": "available",
            "drone_api_key": f"api-{name}",
            "drone_response_key": f"response-{name}",
        }
        values.update(vals)
        return cls.Controller.create(values)

    def setUp(self):
        super().setUp()
        self.network.reset()

    # Helpers
    def real_defer_handlers(self):
        """Use the defer handlers of all installed modules."""
        return patch.object(
            type(self.Server),
            "_get_command_defer_handlers",
            self.original_defer_handlers,
        )

    def run_postcommit(self):
        """Run callbacks registered on postcommit, as a real commit would."""
        self.env.flush_all()
        self.env.cr.postcommit.run()
        self.env.invalidate_all()

    def run_command(self, command=None, server=None):
        """Run a command and return its log."""
        command = command or self.command_ssh
        server = server or self.server_test_1
        server.run_command(command)
        return self.CommandLog.search(
            [("command_id", "=", command.id), ("server_id", "=", server.id)],
            order="id desc",
            limit=1,
        )

    def dispatch(self, command=None, server=None):
        """Run a command, submit its job and return (log, job)."""
        log = self.run_command(command=command, server=server)
        self.run_postcommit()
        return log, log.sudo().drone_job_id

    def decrypt(self, post):
        """Return the envelope of a submission POST to the first controller."""
        key = self.controller_1.sudo()._get_secret_value("payload_key")
        return json.loads(
            Fernet(key.encode()).decrypt(post["json"]["payload"].encode())
        )

    def http_result(self, job, **vals):
        """Send a result as the first controller would, return the HTTP status."""
        data = {
            "nonce": job.sudo().nonce,
            "state": "finished",
            "status": 0,
            "response": "ok",
            "error": None,
        }
        data.update(vals)
        token = self.controller_1.sudo()._get_secret_value("drone_response_key")
        status = self.Job._http_result(token, data)
        self.env.invalidate_all()
        return status
