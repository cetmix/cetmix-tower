# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import patch

import requests
from cryptography.fernet import Fernet
from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tools import mute_logger

from .common import CONTROLLER_LOGGER, TestDroneCommon, connection_refused


class TestDroneController(TestDroneCommon):
    def test_payload_key_generated(self):
        key = self.controller_1._get_secret_value("payload_key")
        self.assertTrue(key)
        # Valid Fernet key
        Fernet(key.encode())
        given_key = Fernet.generate_key().decode()
        controller = self._create_controller("Keyed", payload_key=given_key)
        self.assertEqual(controller._get_secret_value("payload_key"), given_key)

    def test_invalid_payload_key_rejected(self):
        with self.assertRaises(ValidationError):
            self._create_controller("Bad Key", payload_key="given-key")
        with self.assertRaises(ValidationError):
            self.controller_1.write({"payload_key": "given-key"})
        new_key = Fernet.generate_key().decode()
        self.controller_1.write({"payload_key": new_key})
        self.assertEqual(self.controller_1._get_secret_value("payload_key"), new_key)

    def test_action_generate_keys(self):
        """Generate stores three keys and shows a storage key without saving it."""
        old = {
            name: self.controller_1._get_secret_value(name)
            for name in ("drone_api_key", "payload_key", "drone_response_key")
        }
        action = self.controller_1.action_generate_keys()
        stored = {
            name: self.controller_1._get_secret_value(name)
            for name in ("drone_api_key", "payload_key", "drone_response_key")
        }
        self.assertEqual(len(set(stored.values())), 3)
        for name, value in stored.items():
            self.assertNotEqual(value, old[name])
            self.assertTrue(value)
        Fernet(stored["payload_key"].encode())
        self.assertEqual(len(stored["drone_api_key"]), 43)
        self.assertEqual(len(stored["drone_response_key"]), 43)
        self.assertNotIn("result_storage_key", self.controller_1._fields)
        storage_key = action["context"]["default_result_storage_key"]
        self.assertEqual(len(storage_key), 64)
        self.assertTrue(all(char in "0123456789abcdef" for char in storage_key))
        self.assertNotIn(storage_key, stored.values())
        self.assertEqual(action["res_model"], "cx.tower.drone.payload.key.wizard")
        self.assertEqual(action["target"], "new")
        context = action["context"]
        self.assertEqual(context["default_drone_api_key"], stored["drone_api_key"])
        self.assertEqual(context["default_payload_key"], stored["payload_key"])
        self.assertEqual(
            context["default_drone_response_key"], stored["drone_response_key"]
        )
        wizard = self.env[action["res_model"]].browse(action["res_id"])
        self.assertEqual(wizard.controller_id, self.controller_1)
        shown_names = list(stored) + ["result_storage_key"]
        for name in shown_names:
            self.assertFalse(wizard._fields[name].store)
        # The form reads the wizard with the action context, as web_read does.
        shown = wizard.with_context(**context).read(shown_names)
        for name, value in stored.items():
            self.assertEqual(shown[0][name], value)
        self.assertEqual(shown[0]["result_storage_key"], storage_key)
        # Plaintext keys are not written to the transient table, and the
        # controller columns stay empty because the vault holds the values.
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT drone_api_key, payload_key, drone_response_key "
            "FROM cx_tower_drone_controller WHERE id = %s",
            [self.controller_1.id],
        )
        self.assertEqual(self.env.cr.fetchone(), (None, None, None))
        self.env.invalidate_all()
        hidden = wizard.read(shown_names)[0]
        for name in shown_names:
            self.assertFalse(hidden[name])

    @mute_logger("odoo.sql_db")
    def test_max_running_jobs_not_negative(self):
        with self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self.controller_1.max_running_jobs = -1
            self.env.flush_all()

    def test_keys_are_vault_backed(self):
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT drone_api_key, payload_key, drone_response_key "
            "FROM cx_tower_drone_controller WHERE id = %s",
            [self.controller_1.id],
        )
        self.assertEqual(self.env.cr.fetchone(), (None, None, None))
        self.assertEqual(
            self.controller_1._get_secret_value("drone_api_key"), "api-Controller 1"
        )
        self.controller_1.invalidate_recordset()
        self.assertEqual(
            self.controller_1.drone_response_key,
            self.controller_1.SECRET_VALUE_PLACEHOLDER,
        )

    def test_callback_url_defaults_to_web_base(self):
        """A new controller stores the Odoo web base URL."""
        self.env["ir.config_parameter"].sudo().set_param(
            "web.base.url", "https://tower.example.com/"
        )
        controller = self.Controller.create(
            {
                "name": "Default Callback",
                "controller_url": "https://default-callback.example.com",
            }
        )
        self.assertEqual(controller.callback_url, "https://tower.example.com")

    def test_callback_url_origin(self):
        """Callback URL is an absolute http(s) origin, or empty."""
        self.controller_1.callback_url = "http://odoo:8069"
        self.controller_1.callback_url = False
        for value in (
            "odoo:8069",
            "ftp://odoo:8069",
            "http://odoo:8069/cetmix_tower_drone/job/result",
            "http://user:secret@odoo:8069",
        ):
            with self.assertRaises(ValidationError):
                self.controller_1.callback_url = value

    def test_default_status(self):
        controller = self.Controller.create(
            {
                "name": "Fresh",
                "controller_url": "https://fresh.example.com",
                "skill_ids": [(6, 0, [self.skill.id])],
            }
        )
        self.assertEqual(controller.status, "not_reachable")

    def test_skill_reference_not_checked_against_registry(self):
        """Any reference matching the token pattern can be stored."""
        skill = self.Skill.create({"name": "Custom", "reference": "not_registered"})
        self.assertEqual(skill.reference, "not_registered")

    def test_controller_saved_without_skills(self):
        controller = self.Controller.create(
            {
                "name": "No Skills",
                "controller_url": "https://noskills.example.com",
            }
        )
        self.assertFalse(controller.skill_ids)

    def test_running_job_count(self):
        self.launch()
        job = self.launch().sudo()
        self.env.cr.postcommit.clear()
        self.make_running(job)
        self.controller_1.invalidate_recordset()
        self.assertEqual(self.controller_1.running_job_count, 2)
        job._cancel()
        self.controller_1.invalidate_recordset()
        self.assertEqual(self.controller_1.running_job_count, 1)

    def test_action_view_jobs(self):
        """job_count includes jobs that are no longer pending or running."""
        self.launch()
        job = self.launch().sudo()
        self.env.cr.postcommit.clear()
        job._cancel()
        self.controller_1.invalidate_recordset()
        self.assertEqual(self.controller_1.running_job_count, 1)
        self.assertEqual(self.controller_1.job_count, 2)
        action = self.controller_1.action_view_jobs()
        self.assertEqual(action["res_model"], "cx.tower.drone.job")
        self.assertEqual(
            action["domain"], [("controller_id", "=", self.controller_1.id)]
        )

    def test_reservation_bumps_token(self):
        seq = self.controller_1.reservation_seq
        self.assertTrue(self.controller_1._reserve())
        self.assertEqual(self.controller_1.reservation_seq, seq + 1)

    # ------------------------------
    # Health
    # ------------------------------
    def test_health_ok(self):
        self.controller_1.status = "error"
        self.Controller._cron_check_health()
        self.assertEqual(self.controller_1.status, "available")
        self.assertTrue(self.controller_1.last_health_check)

    @mute_logger(CONTROLLER_LOGGER)
    def test_cron_health_isolates_failures(self):
        """One controller raising does not stop checks for the others."""
        checked = []
        original = type(self.Controller)._check_health

        def flaky(controller):
            checked.append(controller.id)
            if controller == self.controller_1:
                raise RuntimeError("boom")
            return original(controller)

        with patch.object(type(self.Controller), "_check_health", flaky):
            self.Controller._cron_check_health()
        self.assertEqual(checked, [self.controller_1.id, self.controller_2.id])
        self.assertEqual(self.controller_2.status, "available")
        self.assertTrue(self.controller_2.last_health_check)

    @mute_logger(CONTROLLER_LOGGER)
    def test_health_connection_error(self):
        for exc in (connection_refused(), requests.exceptions.ReadTimeout()):
            self.controller_1.status = "available"
            self.network.set(self.controller_1, health=exc)
            self.Controller._cron_check_health()
            self.assertEqual(self.controller_1.status, "not_reachable")

    def test_health_other_http(self):
        self.network.set(self.controller_1, health=500)
        self.Controller._cron_check_health()
        self.assertEqual(self.controller_1.status, "error")

    def test_health_never_overwrites_draining(self):
        self.controller_1.status = "draining"
        for answer in (200, 500, connection_refused()):
            self.network.set(self.controller_1, health=answer)
            self.Controller._cron_check_health()
            self.assertEqual(self.controller_1.status, "draining")
        self.assertFalse(
            self.network.find("GET", "/health", base=self.controller_1.controller_url)
        )

    def test_action_check_health(self):
        """The form button checks the connection and reports the status."""
        self.controller_1.status = "error"
        action = self.controller_1.action_check_health()
        self.assertEqual(self.controller_1.status, "available")
        self.assertTrue(self.controller_1.last_health_check)
        self.assertEqual(action["params"]["type"], "success")
        self.assertIn("Available", action["params"]["message"])
        self.assertEqual(
            len(
                self.network.find(
                    "GET", "/health", base=self.controller_1.controller_url
                )
            ),
            1,
        )

    def test_action_check_health_not_reachable(self):
        """A controller that does not answer is reported as a warning."""
        self.network.set(self.controller_1, health=500)
        action = self.controller_1.action_check_health()
        self.assertEqual(self.controller_1.status, "error")
        self.assertEqual(action["params"]["type"], "warning")
        self.assertIn("Error", action["params"]["message"])

    def test_action_check_health_inactive_and_draining(self):
        """The button checks controllers the cron skips."""
        self.controller_1.active = False
        self.controller_1.action_check_health()
        self.assertEqual(self.controller_1.status, "available")

        self.controller_1.write({"active": True, "status": "draining"})
        action = self.controller_1.action_check_health()
        self.assertEqual(self.controller_1.status, "draining")
        self.assertEqual(action["params"]["type"], "success")
        self.assertEqual(
            len(
                self.network.find(
                    "GET", "/health", base=self.controller_1.controller_url
                )
            ),
            2,
        )

    def test_health_skips_inactive(self):
        self.controller_1.active = False
        self.Controller._cron_check_health()
        self.assertFalse(
            self.network.find("GET", "/health", base=self.controller_1.controller_url)
        )

    def test_health_replaces_skills(self):
        """A valid body creates skills, then a later body drops one link."""
        self.network.set(
            self.controller_1,
            health=(200, {"skills": ["sync", "sync", "backup"], "version": 1}),
        )
        self.assertTrue(self.controller_1._check_health())
        skills = self.controller_1.skill_ids
        self.assertEqual(set(skills.mapped("reference")), {"sync", "backup"})
        sync = skills.filtered(lambda skill: skill.reference == "sync")
        backup = skills.filtered(lambda skill: skill.reference == "backup")
        self.assertEqual(sync.name, "sync")
        self.assertEqual(backup.name, "backup")
        sync.name = "File Sync"
        self.network.set(self.controller_1, health=(200, {"skills": ["sync"]}))
        self.assertTrue(self.controller_1._check_health())
        self.assertEqual(self.controller_1.skill_ids, sync)
        self.assertEqual(sync.name, "File Sync")
        self.assertTrue(backup.exists())
        self.assertFalse(self.controller_1.skill_ids & backup)

    @mute_logger(CONTROLLER_LOGGER)
    def test_health_invalid_body_leaves_skills(self):
        """A bad 200 or a connection error does not replace the skills."""
        skills = self.controller_1.skill_ids
        checked = self.controller_1.last_health_check
        for answer in (
            (200, {"skills": ["SSH"]}),
            (200, {"ok": True}),
            (200, ["ssh"]),
            200,
        ):
            self.controller_1.status = "available"
            self.network.set(self.controller_1, health=answer)
            self.assertFalse(self.controller_1._check_health())
            self.assertEqual(self.controller_1.status, "error")
            self.assertEqual(self.controller_1.skill_ids, skills)
            self.assertEqual(self.controller_1.last_health_check, checked)

        self.controller_1.status = "available"
        self.network.set(self.controller_1, health=connection_refused())
        self.assertFalse(self.controller_1._check_health())
        self.assertEqual(self.controller_1.status, "not_reachable")
        self.assertEqual(self.controller_1.skill_ids, skills)
        self.assertEqual(self.controller_1.last_health_check, checked)

        self.network.set(self.controller_1, health=(200, {"skills": []}))
        self.assertTrue(self.controller_1._check_health())
        self.assertFalse(self.controller_1.skill_ids)
        self.assertEqual(self.controller_1.status, "available")

    def test_health_draining_updates_skills(self):
        """Check Connection stores skills and leaves a draining status."""
        self.controller_1.status = "draining"
        self.network.set(self.controller_1, health=(200, {"skills": ["backup"]}))
        self.controller_1.action_check_health()
        self.assertEqual(self.controller_1.status, "draining")
        self.assertEqual(self.controller_1.skill_ids.mapped("reference"), ["backup"])

    def test_health_lost_skill_insert(self):
        """A unique violation leaves this controller and continues the cron."""
        skills = self.controller_1.skill_ids
        status = self.controller_1.status
        checked = self.controller_1.last_health_check
        controller_cls = type(self.Controller)
        original = controller_cls._check_health
        returns = {}

        def wrapped(controller):
            result = original(controller)
            returns[controller.id] = result
            return result

        def boom(self, vals_list):
            raise IntegrityError()

        self.network.set(self.controller_1, health=(200, {"skills": ["brand_new"]}))
        with (
            patch.object(controller_cls, "_check_health", wrapped),
            patch.object(type(self.Skill), "create", boom),
        ):
            self.Controller._cron_check_health()
        self.controller_1.invalidate_recordset()
        self.assertFalse(returns[self.controller_1.id])
        self.assertTrue(returns[self.controller_2.id])
        self.assertEqual(self.controller_1.skill_ids, skills)
        self.assertEqual(self.controller_1.status, status)
        self.assertEqual(self.controller_1.last_health_check, checked)
        self.assertFalse(self.Skill.search([("reference", "=", "brand_new")]))

    def test_outbound_auth_header_and_timeout(self):
        self.controller_1._check_health()
        call = self.network.find(
            "GET", "/health", base=self.controller_1.controller_url
        )[0]
        self.assertEqual(call["headers"], {"Authorization": "Bearer api-Controller 1"})
        self.assertEqual(call["timeout"], (10, 10))
        self.assertFalse(call["allow_redirects"])

    # ------------------------------
    # Inbound status
    # ------------------------------
    def test_http_status(self):
        Controller = self.Controller
        reference = self.controller_1.reference
        token = "response-Controller 1"
        self.assertEqual(
            Controller._http_status(token, {"reference": "nope", "status": "error"}),
            404,
        )
        self.assertEqual(
            Controller._http_status(
                "wrong", {"reference": reference, "status": "error"}
            ),
            403,
        )
        self.assertEqual(
            Controller._http_status(
                "response-Controller 2", {"reference": reference, "status": "error"}
            ),
            403,
        )
        self.assertEqual(
            Controller._http_status(
                token, {"reference": reference, "status": "draining"}
            ),
            400,
        )
        self.assertEqual(
            Controller._http_status(token, {"reference": reference, "status": "error"}),
            200,
        )
        self.assertEqual(self.controller_1.status, "error")
        self.controller_1.status = "draining"
        self.assertEqual(
            Controller._http_status(
                token, {"reference": reference, "status": "available"}
            ),
            409,
        )
        self.assertEqual(self.controller_1.status, "draining")
