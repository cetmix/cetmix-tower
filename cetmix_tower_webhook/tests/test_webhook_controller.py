# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json
from unittest.mock import patch

from odoo.tests import HttpCase, tagged


@tagged("-at_install", "post_install")
class TestCxTowerWebhookController(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # Authenticator that always allows requests
        cls.authenticator = env["cx.tower.webhook.authenticator"].create(
            {"name": "Always OK", "code": "result = {'allowed': True}"}
        )
        # POST webhook
        cls.webhook_post = env["cx.tower.webhook"].create(
            {
                "name": "Test Webhook POST",
                "endpoint": "webhook_post",
                "method": "post",
                "authenticator_id": cls.authenticator.id,
                "code": "result = {'exit_code': 0, 'message': 'POST ok'}",
            }
        )
        # GET webhook
        cls.webhook_get = env["cx.tower.webhook"].create(
            {
                "name": "Test Webhook GET",
                "endpoint": "webhook_get",
                "method": "get",
                "authenticator_id": cls.authenticator.id,
                "code": "result = {'exit_code': 0, 'message': 'GET ok'}",
            }
        )
        # Log model
        cls.Log = env["cx.tower.webhook.log"]

    def url_for(self, endpoint):
        """Helper to build webhook url"""
        url = f"/cetmix_tower_webhooks/{endpoint}"
        return self.base_url() + url

    def assert_log(self, log=None, request_payload=None, **expected):
        """
        Universal log checker for webhook log model.
        Checks expected field values and substrings.
        """
        self.assertIsNotNone(log, "Log record was not created")
        if request_payload is not None:
            try:
                log_payload = log.request_payload
                # try to convert both to Python dict for comparison
                if isinstance(log_payload, str):
                    log_payload = log_payload.strip()
                self.assertDictEqual(
                    json.loads(
                        log_payload.replace("'", '"')
                    ),  # try to make JSON from possible str(dict)
                    json.loads(request_payload),
                )
            except Exception as ex:
                self.fail(
                    f"Payload comparison failed: {ex}\nLog: {log.request_payload}\nExpected: {request_payload}"  # noqa: E501
                )
        for field, value in expected.items():
            if field == "request_payload":
                continue  # Already checked
            actual = getattr(log, field)
            self.assertEqual(actual, value, f"{field}: expected {value}, got {actual}")

    def test_post_webhook_success(self):
        """Success test for POST request with correct payload."""
        data = json.dumps({"some": "data"})
        response = self.url_open(
            self.url_for(self.webhook_post.endpoint),
            data=data,
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"POST ok", response.content)

        log = self.Log.search([("webhook_id", "=", self.webhook_post.id)])
        self.assert_log(
            log,
            code_status="success",
            authentication_status="success",
            http_status=200,
            endpoint=self.webhook_post.endpoint,
            request_payload=data,
        )

    def test_get_webhook_success(self):
        """Success test for GET request with correct payload."""
        response = self.url_open(
            f"{self.url_for(self.webhook_get.endpoint)}?foo=bar",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"GET ok", response.content)

        log = self.Log.search([("webhook_id", "=", self.webhook_get.id)])
        self.assert_log(
            log,
            code_status="success",
            authentication_status="success",
            http_status=200,
            endpoint=self.webhook_get.endpoint,
        )
        self.assertIn("foo", log.request_payload)

    def test_webhook_not_found(self):
        """Test request to a non-existing webhook endpoint."""
        data = json.dumps({"test": 1})
        response = self.url_open(
            self.url_for("missing"),
            data=data,
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn(b"Webhook not found", response.content)

        log = self.Log.search([("webhook_id", "=", False)])
        self.assert_log(
            log,
            code_status="skipped",
            authentication_status="failed",
            http_status=404,
            endpoint="missing",
            error_message="Webhook not found",
            request_payload=data,
        )

    def test_wrong_method(self):
        """
        Test GET request to POST-only webhook.
        """
        response = self.url_open(
            self.url_for(self.webhook_post.endpoint),
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn(b"Webhook not found", response.content)

        log = self.Log.search([("webhook_id", "=", False)])
        self.assert_log(
            log,
            code_status="skipped",
            authentication_status="failed",
            http_status=404,
            error_message="Webhook not found",
            endpoint=self.webhook_post.endpoint,
            request_method="get",
        )

    def test_missing_payload_post(self):
        """
        Test POST request with empty payload.
        """
        # use opener instead of url_open to avoid checking of data
        response = self.opener.post(
            self.url_for(self.webhook_post.endpoint),
            timeout=1200000,
            headers={"Content-Type": "application/json"},
            allow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"POST ok", response.content)

        log = self.Log.search([("webhook_id", "=", self.webhook_post.id)])
        self.assert_log(
            log,
            code_status="success",
            authentication_status="success",
            http_status=200,
            endpoint=self.webhook_post.endpoint,
            request_payload="{}",
        )

    def test_authentication_failed(self):
        """
        Test POST request with authenticator that always denies.
        """
        bad_auth = self.env["cx.tower.webhook.authenticator"].create(
            {
                "name": "Never OK",
                "code": "result = {'allowed': False, 'custom_message': 'Forbidden'}",
            }
        )
        webhook = self.env["cx.tower.webhook"].create(
            {
                "name": "Forbidden Webhook",
                "endpoint": "forbidden",
                "method": "post",
                "authenticator_id": bad_auth.id,
                "code": "result = {'exit_code': 0, 'message': 'Should not run'}",
            }
        )
        data = json.dumps({"fail": 1})
        response = self.url_open(
            self.url_for(webhook.endpoint),
            data=data,
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn(b"Authentication not allowed", response.content)

        log = self.Log.search([("webhook_id", "=", webhook.id)])
        self.assert_log(
            log,
            code_status="skipped",
            authentication_status="failed",
            http_status=403,
            endpoint=webhook.endpoint,
            request_payload=data,
        )

    def test_webhook_code_failure(self):
        """
        Test POST request to a webhook that raises an exception in code.
        """
        self.webhook_post.code = "raise Exception('Some error!')"
        response = self.url_open(
            self.url_for(self.webhook_post.endpoint),
            data=json.dumps({}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 500)
        self.assertIn(b"Some error!", response.content)

        log = self.Log.search([("webhook_id", "=", self.webhook_post.id)])
        self.assert_log(
            log,
            code_status="failed",
            authentication_status="success",
            http_status=500,
            endpoint=self.webhook_post.endpoint,
            request_payload="{}",
        )
        self.assertIn("Some error!", log.error_message)

    def test_json_headers_are_stored(self):
        """
        Test that request headers and payload are saved in webhook log record.
        """
        payload = {"foo": "bar"}
        headers = {"X-Test-Header": "xxx", "Content-Type": "application/json"}
        response = self.url_open(
            self.url_for(self.webhook_post.endpoint),
            data=json.dumps(payload),
            headers=headers,
        )

        log = self.Log.search([("webhook_id", "=", self.webhook_post.id)])
        self.assert_log(
            log,
            code_status="success",
            authentication_status="success",
            http_status=200,
            endpoint=self.webhook_post.endpoint,
        )
        self.assertIn("foo", log.request_payload)
        self.assertIn("X-Test-Header", log.request_headers)
        self.assertIn(log.result_message, response.text)

    def test_log_contains_ip(self):
        """
        Test that the log contains the client's IP address and country (if available).
        """
        payload = {"check": "ip"}
        self.url_open(
            self.url_for(self.webhook_post.endpoint),
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

        log = self.Log.search([("webhook_id", "=", self.webhook_post.id)])
        self.assertTrue(log.ip_address)

    def test_inactive_webhook(self):
        """Test that inactive webhooks are not callable."""
        self.webhook_post.active = False
        response = self.url_open(
            self.url_for(self.webhook_post.endpoint),
            data=json.dumps({"a": 1}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn(b"Webhook not found", response.content)

    def test_authenticator_code_raises(self):
        """
        Test that if authenticator's code raises an error,
        proper log is created and 403 returned.
        """
        bad_auth = self.env["cx.tower.webhook.authenticator"].create(
            {"name": "Broken Auth", "code": "raise Exception('auth fail')"}
        )
        webhook = self.env["cx.tower.webhook"].create(
            {
                "name": "Web with bad auth",
                "endpoint": "bad_auth",
                "method": "post",
                "authenticator_id": bad_auth.id,
                "code": "result = {'exit_code': 0, 'message': 'Should not run'}",
            }
        )
        response = self.url_open(
            self.url_for(webhook.endpoint),
            data=json.dumps({"x": 1}),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertIn(b"auth fail", response.content)

        log = self.Log.search([("webhook_id", "=", webhook.id)])
        self.assert_log(
            log,
            code_status="skipped",
            authentication_status="failed",
            http_status=403,
            endpoint=webhook.endpoint,
        )
        self.assertIn("auth fail", log.error_message)

    def test_post_webhook_json_content_type(self):
        """
        Test POST request with content_type json.
        """
        self.webhook_post.content_type = "json"
        self.webhook_post.code = "result = {'exit_code': 0, 'message': 'POST JSON ok'}"

        data = json.dumps({"json_test": "ok"})
        response = self.url_open(
            self.url_for(self.webhook_post.endpoint),
            data=data,
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"POST JSON ok", response.content)

        log = self.Log.search([("webhook_id", "=", self.webhook_post.id)])
        self.assert_log(
            log,
            code_status="success",
            authentication_status="success",
            http_status=200,
            endpoint=self.webhook_post.endpoint,
            request_payload=data,
        )

    def test_post_webhook_form_content_type(self):
        """
        Test POST request with content_type form.
        """
        self.webhook_post.content_type = "form"
        self.webhook_post.code = "result = {'exit_code': 0, 'message': 'POST FORM ok'}"

        data = {"form_field": "ok"}
        response = self.url_open(
            self.url_for(self.webhook_post.endpoint),
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"POST FORM ok", response.content)

        log = self.Log.search([("webhook_id", "=", self.webhook_post.id)])
        self.assertIn("form_field", log.request_payload)

    def test_authenticator_ipv4_and_ipv6(self):
        """
        Test IP filter for IPv4, IPv6, and networks
        by monkeypatching REMOTE_ADDR in environ.
        """
        auth = self.env["cx.tower.webhook.authenticator"].create(
            {
                "name": "IP Test",
                "allowed_ip_addresses": "203.0.113.5,2001:db8::42,198.51.100.0/24,2001:db8:abcd::/48",  # noqa: E501
                "code": "result = {'allowed': True}",
            }
        )
        webhook = self.env["cx.tower.webhook"].create(
            {
                "name": "IP Webhook",
                "endpoint": "webhook_iptest",
                "method": "post",
                "authenticator_id": auth.id,
                "code": "result = {'exit_code': 0, 'message': 'IP OK'}",
            }
        )

        data = json.dumps({"ip": "test"})

        def do_req(ip):
            # Patch _get_remote_addr to simulate requests coming
            # from different IP addresses
            with patch(
                "odoo.addons.cetmix_tower_webhook.controllers.main.CetmixTowerWebhookController._get_remote_addr",
                return_value=ip,
            ):
                return self.url_open(
                    self.url_for(webhook.endpoint),
                    data=data,
                    headers={"Content-Type": "application/json"},
                )

        # IPv4 address allowed
        resp = do_req("203.0.113.5")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"IP OK", resp.content)

        # IPv6 address allowed
        resp = do_req("2001:db8::42")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"IP OK", resp.content)

        # IPv4 network allowed
        resp = do_req("198.51.100.99")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"IP OK", resp.content)

        # IPv6 network allowed
        resp = do_req("2001:db8:abcd::abcd")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"IP OK", resp.content)

        # Denied IPv4 address
        resp = do_req("203.0.113.99")
        self.assertEqual(resp.status_code, 403)
        self.assertIn(b"Address not allowed", resp.content)

        # Denied IPv6 address
        resp = do_req("2001:db8:ffff::1")
        self.assertEqual(resp.status_code, 403)
        self.assertIn(b"Address not allowed", resp.content)

    def _make_proxy_webhook(
        self,
        allowed,
        trusted=None,
        code="result = {'exit_code': 0, 'message': 'OK via proxy'}",
    ):
        """
        Helper to create a webhook with a dedicated authenticator configured
        for proxy-aware tests.
        """
        auth = self.env["cx.tower.webhook.authenticator"].create(
            {
                "name": "Proxy Aware",
                "allowed_ip_addresses": allowed,
                "trusted_proxy_ips": trusted or "",
                "code": "result = {'allowed': True}",
            }
        )
        wh = self.env["cx.tower.webhook"].create(
            {
                "name": "Proxy Webhook",
                "endpoint": "proxy_webhook",
                "method": "post",
                "authenticator_id": auth.id,
                "code": code,
            }
        )
        return wh, auth

    def test_proxy_headers_ignored_without_trusted_proxy(self):
        """
        When trusted_proxy_ips is empty, XFF/X-Real-IP must be ignored.
        We fallback to immediate peer (proxy IP), which is not allowed -> 403.
        """
        # Allow only the real client network, not the proxy itself
        webhook, _auth = self._make_proxy_webhook(
            allowed="203.0.113.0/24", trusted=None
        )

        data = json.dumps({"k": "v"})
        proxy_ip = "10.0.0.5"  # immediate peer (undocumented as trusted)
        headers = {
            "Content-Type": "application/json",
            "X-Forwarded-For": "203.0.113.7, 10.0.0.5",  # should be ignored
            "X-Real-IP": "203.0.113.7",  # should be ignored
        }
        with patch(
            "odoo.addons.cetmix_tower_webhook.controllers.main.CetmixTowerWebhookController._get_remote_addr",
            return_value=proxy_ip,
        ):
            resp = self.url_open(
                self.url_for(webhook.endpoint), data=data, headers=headers
            )

        self.assertEqual(resp.status_code, 403)
        self.assertIn(b"Address not allowed", resp.content)

    def test_proxy_xff_honored_with_trusted_proxy(self):
        """
        With trusted proxy configured, take the left-most IP from X-Forwarded-For.
        """
        webhook, _auth = self._make_proxy_webhook(
            allowed="203.0.113.0/24",
            trusted="10.0.0.5",
            code="result = {'exit_code': 0, 'message': 'OK XFF'}",
        )

        data = json.dumps({"k": "v"})
        proxy_ip = "10.0.0.5"
        headers = {
            "Content-Type": "application/json",
            # XFF list: client, proxy
            "X-Forwarded-For": "203.0.113.7, 10.0.0.5",
        }
        with patch(
            "odoo.addons.cetmix_tower_webhook.controllers.main.CetmixTowerWebhookController._get_remote_addr",
            return_value=proxy_ip,
        ):
            resp = self.url_open(
                self.url_for(webhook.endpoint), data=data, headers=headers
            )

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"OK XFF", resp.content)

    def test_proxy_x_real_ip_fallback_when_xff_missing(self):
        """
        If XFF is missing/invalid but trusted proxy is set, fall back to X-Real-IP.
        """
        webhook, _auth = self._make_proxy_webhook(
            allowed="203.0.113.0/24",
            trusted="10.0.0.5",
            code="result = {'exit_code': 0, 'message': 'OK X-Real-IP'}",
        )

        data = json.dumps({"k": "v"})
        proxy_ip = "10.0.0.5"
        headers = {
            "Content-Type": "application/json",
            "X-Forwarded-For": "garbage, not_an_ip",  # invalids should be skipped
            "X-Real-IP": "203.0.113.8",
        }
        with patch(
            "odoo.addons.cetmix_tower_webhook.controllers.main.CetmixTowerWebhookController._get_remote_addr",
            return_value=proxy_ip,
        ):
            resp = self.url_open(
                self.url_for(webhook.endpoint), data=data, headers=headers
            )

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"OK X-Real-IP", resp.content)

    def test_proxy_invalid_headers_fall_back_to_immediate_peer(self):
        """
        If headers are invalid even with trusted proxy, fall back to immediate peer.
        Since the proxy IP is not in allowlist, the request is denied.
        """
        webhook, _auth = self._make_proxy_webhook(
            allowed="203.0.113.0/24",  # does NOT include proxy IP
            trusted="10.0.0.5",
        )

        data = json.dumps({"k": "v"})
        proxy_ip = "10.0.0.5"
        headers = {
            "Content-Type": "application/json",
            "X-Forwarded-For": "not_an_ip, also_bad",
            "X-Real-IP": "bad_ip_value",
        }
        with patch(
            "odoo.addons.cetmix_tower_webhook.controllers.main.CetmixTowerWebhookController._get_remote_addr",
            return_value=proxy_ip,
        ):
            resp = self.url_open(
                self.url_for(webhook.endpoint), data=data, headers=headers
            )

        self.assertEqual(resp.status_code, 403)
        self.assertIn(b"Address not allowed", resp.content)

    def test_proxy_allows_via_immediate_peer_when_proxy_ip_in_allowlist(self):
        """
        If headers are ignored/invalid, but the proxy IP itself is allowed,
        access should be granted based on immediate peer.
        """
        webhook, _auth = self._make_proxy_webhook(
            allowed="10.0.0.5",  # allow the proxy itself
            trusted="",  # no trusted proxies => headers ignored
            code="result = {'exit_code': 0, 'message': 'OK immediate peer'}",
        )

        data = json.dumps({"k": "v"})
        proxy_ip = "10.0.0.5"
        headers = {
            "Content-Type": "application/json",
            "X-Forwarded-For": "203.0.113.7",  # should be ignored
        }
        with patch(
            "odoo.addons.cetmix_tower_webhook.controllers.main.CetmixTowerWebhookController._get_remote_addr",
            return_value=proxy_ip,
        ):
            resp = self.url_open(
                self.url_for(webhook.endpoint), data=data, headers=headers
            )

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"OK immediate peer", resp.content)
