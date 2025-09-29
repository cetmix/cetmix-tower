# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError

from .common import CetmixTowerWebhookCommon


class TestCetmixTowerWebhookAuthenticator(CetmixTowerWebhookCommon):
    def test_simple_authentication_success(self):
        """
        Test that authentication is successful
        """
        # check that authentication is successful for authenticator
        # that allows all requests
        result = self.simple_authenticator.authenticate(
            headers={}, payload={}, raw_data=""
        )
        self.assertTrue(result["allowed"])

    def test_simple_authentication_without_optional_params(self):
        """
        Test that authentication is successful without optional params
        """
        result = self.simple_authenticator.authenticate()
        self.assertTrue(result["allowed"])

    def test_token_authentication_success(self):
        """
        Test that authentication is successful for authenticator that allows requests
        with specific token in header
        """
        auth_token_header = "X-Token"
        auth_token = "secret123"
        code = f"result = {{'allowed': headers.get('{auth_token_header}') == '{auth_token}'}}"  # noqa: E501
        self.simple_authenticator.code = code
        result = self.simple_authenticator.authenticate(
            headers={auth_token_header: auth_token}
        )
        self.assertTrue(result["allowed"])

    def test_token_authentication_failure(self):
        """
        Test that authentication is failed for authenticator that allows
        requests with specific token in header
        """
        auth_token_header = "X-Token"
        auth_token = "secret123"
        code = f"result = {{'allowed': headers.get('{auth_token_header}') == '{auth_token}'}}"  # noqa: E501
        self.simple_authenticator.code = code
        result = self.simple_authenticator.authenticate(
            headers={auth_token_header: "wrong_token"}, raise_on_error=False
        )
        self.assertFalse(result["allowed"])

    def test_token_authentication_failure_without_optional_params(self):
        """
        Test that authentication is failed without optional params
        """
        auth_token_header = "X-Token"
        auth_token = "secret123"
        code = f"result = {{'allowed': headers.get('{auth_token_header}') == '{auth_token}'}}"  # noqa: E501
        self.simple_authenticator.code = code
        result = self.simple_authenticator.authenticate(raise_on_error=False)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["http_code"], 500)
        self.assertIn("object has no attribute 'get'", result["message"])

    def test_authentication_code_error(self):
        """
        Test that authentication is failed with invalid code
        """
        self.simple_authenticator.code = "1/0"
        result = self.simple_authenticator.authenticate(raise_on_error=False)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["http_code"], 500)
        self.assertEqual(result["message"], "division by zero")

        # test with raise_on_error=True
        with self.assertRaises(ValidationError) as e:
            self.simple_authenticator.authenticate()
        self.assertEqual(
            str(e.exception), "Authentication code error: division by zero"
        )

    def test_authenticator_custom_http_code_and_message(self):
        """
        Test that custom http_code and message returned from code are respected
        """
        message = "I am a teapot!"
        self.simple_authenticator.code = (
            f"result = {{'allowed': False, 'http_code': 418, 'message': '{message}'}}"
        )
        result = self.simple_authenticator.authenticate(headers={})
        self.assertFalse(result["allowed"])
        self.assertEqual(result.get("http_code"), 418)
        self.assertEqual(result.get("message"), message)

    def test_authenticator_returns_non_dict(self):
        """
        Test that authentication fails if code returns non-dict result
        """
        self.simple_authenticator.write({"code": "result = 'not a dict'"})
        result = self.simple_authenticator.authenticate(
            headers={}, raise_on_error=False
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["http_code"], 500)
        self.assertIn("result is not a dict", result["message"])

    def test_authentication_with_raw_data(self):
        """
        Test that authentication works with raw_data and without headers
        """
        self.simple_authenticator.write(
            {"code": "result = {'allowed': raw_data == 'magic'}"}
        )
        result = self.simple_authenticator.authenticate(raw_data="magic")
        self.assertTrue(result["allowed"])
        result = self.simple_authenticator.authenticate(raw_data="not_magic")
        self.assertFalse(result["allowed"])

    def test_authentication_code_exception(self):
        """
        Test that authentication code exception is captured in result['message']
        """
        self.simple_authenticator.write({"code": "raise Exception('custom failure')"})
        result = self.simple_authenticator.authenticate(
            headers={}, raise_on_error=False
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["http_code"], 500)
        self.assertIn("custom failure", result["message"])

    def test_authentication_minimal_false(self):
        """
        Test minimal code with only allowed: False
        """
        self.simple_authenticator.write({"code": "result = {'allowed': False}"})
        result = self.simple_authenticator.authenticate(headers={})
        self.assertFalse(result["allowed"])
        self.assertIsNone(result.get("http_code"))
        self.assertIsNone(result.get("message"))
