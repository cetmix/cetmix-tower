# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import patch

import requests
from urllib3.exceptions import MaxRetryError, NewConnectionError

from odoo import api

from odoo.addons.cetmix_tower_base.tests.common import TestTowerBaseCommon

JOB_LOGGER = "odoo.addons.cetmix_tower_drone.models.cx_tower_drone_job"
CONTROLLER_LOGGER = "odoo.addons.cetmix_tower_drone.models.cx_tower_drone_controller"


def connection_refused():
    """Return the exception `requests` raises when a connection is refused."""
    return requests.exceptions.ConnectionError(
        MaxRetryError(None, "/", NewConnectionError(None, "Connection refused"))
    )


class FakeResponse:
    def __init__(self, status_code, data=None):
        self.status_code = status_code
        self._data = data

    def json(self):
        if self._data is None:
            raise ValueError("No JSON")
        return self._data


class FakeDroneNetwork:
    """Answers outbound requests per controller URL and records them.

    An answer is a status code, a (status code, json) tuple, an exception
    to raise, or a callable(method, path, json) returning one of those.
    """

    DEFAULTS = {
        ("POST", "/jobs"): 201,
        ("GET", "/jobs/"): (200, {"state": "running"}),
        ("POST", "/fence"): (200, {"state": "fenced"}),
        ("POST", "/cancel"): 200,
        ("GET", "/health"): (200, {"skills": ["test_skill", "untagged_skill"]}),
    }

    def __init__(self):
        self.reset()

    def reset(self):
        self.calls = []
        self.answers = {}

    def set(self, controller, **answers):
        """Set answers for a controller.

        Keys: post, get, fence, cancel, health.
        """
        keys = {
            "post": ("POST", "/jobs"),
            "get": ("GET", "/jobs/"),
            "fence": ("POST", "/fence"),
            "cancel": ("POST", "/cancel"),
            "health": ("GET", "/health"),
        }
        routes = self.answers.setdefault(controller.controller_url, {})
        for key, answer in answers.items():
            routes[keys[key]] = answer

    def _route(self, method, path):
        if method == "POST" and path.endswith("/fence"):
            return ("POST", "/fence")
        if method == "POST" and path.endswith("/cancel"):
            return ("POST", "/cancel")
        if method == "GET" and path.startswith("/jobs/"):
            return ("GET", "/jobs/")
        return (method, path)

    def request(
        self,
        method,
        url,
        json=None,
        headers=None,
        timeout=None,
        allow_redirects=True,
    ):
        base = next((b for b in self.answers if url.startswith(b)), None)
        path = url[len(base) :] if base else "/" + url.split("/", 3)[-1]
        if base is None:
            base = url[: len(url) - len(path)]
        self.calls.append(
            {
                "method": method,
                "base": base,
                "path": path,
                "json": json,
                "headers": headers,
                "timeout": timeout,
                "allow_redirects": allow_redirects,
            }
        )
        route = self._route(method, path)
        answer = self.answers.get(base, {}).get(route, self.DEFAULTS.get(route, 404))
        if callable(answer) and not isinstance(answer, type):
            answer = answer(method, path, json)
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, tuple):
            return FakeResponse(*answer)
        return FakeResponse(answer)

    def find(self, method=None, path_suffix=None, base=None):
        return [
            call
            for call in self.calls
            if (method is None or call["method"] == method)
            and (path_suffix is None or call["path"].endswith(path_suffix))
            and (base is None or call["base"] == base)
        ]


class TestDroneCommon(TestTowerBaseCommon):
    """Common fixtures for drone tests.

    The callback is a method patched onto `cx.tower.tag`.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not cls.registry.in_test_mode():
            cls.registry.enter_test_mode(cls.cr)
            cls.addClassCleanup(cls.registry.leave_test_mode)

        cls.Job = cls.env["cx.tower.drone.job"]
        cls.Controller = cls.env["cx.tower.drone.controller"]
        cls.Skill = cls.env["cx.tower.drone.skill"]
        cls.Tag = cls.env["cx.tower.tag"]

        # Callback on a model that knows nothing about drones
        cls.callback_calls = []
        cls.callback_mode = "ok"

        def _test_drone_done(self, drone_job, result):
            cls.callback_calls.append(
                {
                    "uid": self.env.uid,
                    "record": self.ids,
                    "job": drone_job.id,
                    "state": drone_job.sudo().state,
                    "result": result,
                }
            )
            if cls.callback_mode == "raise":
                raise ValueError("secret output that must not be stored")
            return cls.callback_mode == "ok"

        @api.model
        def _test_drone_model_done(self, drone_job, result):
            return _test_drone_done(self, drone_job, result)

        cls.startClassPatcher(
            patch.object(
                type(cls.Tag), "_test_drone_done", _test_drone_done, create=True
            )
        )
        cls.startClassPatcher(
            patch.object(
                type(cls.Tag),
                "_test_drone_model_done",
                _test_drone_model_done,
                create=True,
            )
        )

        # Outbound HTTP
        cls.network = FakeDroneNetwork()
        cls.startClassPatcher(
            patch("requests.request", side_effect=cls.network.request)
        )

        # Records
        cls.skill = cls.Skill.create({"name": "Test Skill", "reference": "test_skill"})
        cls.skill_untagged = cls.Skill.create(
            {"name": "Untagged Skill", "reference": "untagged_skill"}
        )
        cls.tag_a = cls.Tag.create({"name": "Drone Tag A"})
        cls.tag_b = cls.Tag.create({"name": "Drone Tag B"})
        cls.target = cls.Tag.create({"name": "Drone Callback Target"})
        cls.controller_1 = cls._create_controller("Controller 1", priority=1)
        cls.controller_2 = cls._create_controller("Controller 2", priority=2)
        cls.env["ir.config_parameter"].sudo().set_param(
            "web.base.url", "https://tower.example.com"
        )

    @classmethod
    def _create_controller(cls, name, **vals):
        values = {
            "name": name,
            "controller_url": f"https://{name.lower().replace(' ', '-')}.example.com",
            "skill_ids": [(6, 0, [cls.skill.id, cls.skill_untagged.id])],
            "status": "available",
            "drone_api_key": f"api-{name}",
            "drone_response_key": f"response-{name}",
        }
        values.update(vals)
        return cls.Controller.create(values)

    def setUp(self):
        super().setUp()
        # Mutable class state shared by the patched methods
        self.network.reset()
        self.callback_calls.clear()
        type(self).callback_mode = "ok"

    # Helpers
    def launch(self, skill="test_skill", target=None, payload=None, timeout=60):
        target = target or self.target
        if payload is None:
            payload = {}
        return target.launch_drone(
            skill,
            target._test_drone_done,
            payload,
            drone_timeout=timeout,
        )

    def run_postcommit(self):
        """Run callbacks registered on postcommit, as a real commit would."""
        self.env.flush_all()
        self.env.cr.postcommit.run()
        self.env.invalidate_all()

    def running_job(self, target=None):
        """Launch a job and mark it running without submitting it."""
        job = self.launch(target=target).sudo()
        self.env.cr.postcommit.clear()
        self.make_running(job)
        return job

    def make_running(self, job, controller=None):
        job.sudo().write(
            {
                "state": "running",
                "controller_id": (controller or job.controller_id).id,
                "last_heartbeat": "2026-01-01 00:00:00",
            }
        )
