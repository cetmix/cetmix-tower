# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

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

    def test_default_status(self):
        controller = self.Controller.create(
            {
                "name": "Fresh",
                "controller_url": "https://fresh.example.com",
                "skill_ids": [(6, 0, [self.skill.id])],
            }
        )
        self.assertEqual(controller.status, "not_reachable")

    def test_skill_code_must_be_registered(self):
        with self.assertRaises(ValidationError):
            self.Skill.create({"name": "Nope", "code": "not_registered"})

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

    def test_health_skips_inactive(self):
        self.controller_1.active = False
        self.Controller._cron_check_health()
        self.assertFalse(
            self.network.find("GET", "/health", base=self.controller_1.controller_url)
        )

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
