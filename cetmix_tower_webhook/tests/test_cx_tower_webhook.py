# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError

from .common import CetmixTowerWebhookCommon


class TestCetmixTowerWebhook(CetmixTowerWebhookCommon):
    def test_simple_webhook_success(self):
        """
        Test that webhook is successful
        """
        result = self.simple_webhook.execute(
            headers={}, payload={}, raw_data="", raise_on_error=False
        )
        self.assertEqual(result["exit_code"], 0)

    def test_simple_webhook_without_optional_params(self):
        """
        Test that webhook is successful without optional params
        """
        result = self.simple_webhook.execute(raise_on_error=False)
        self.assertEqual(result["exit_code"], 0)

    def test_webhook_code_custom_message(self):
        """
        Test that custom message is returned from webhook code
        """
        self.simple_webhook.write(
            {"code": "result = {'exit_code': 0, 'message': 'Webhook OK!'}"}
        )
        result = self.simple_webhook.execute(raise_on_error=False)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["message"], "Webhook OK!")

    def test_webhook_code_failure(self):
        """
        Test that webhook returns error when code sets exit_code != 0
        """
        self.simple_webhook.write(
            {"code": "result = {'exit_code': 42, 'message': 'Error occurred'}"}
        )
        result = self.simple_webhook.execute(raise_on_error=False)
        self.assertEqual(result["exit_code"], 42)
        self.assertEqual(result["message"], "Error occurred")

    def test_webhook_code_raises_exception(self):
        """
        Test that exception in webhook code is handled and returns exit_code 1
        """
        self.simple_webhook.write({"code": "raise Exception('Webhook boom!')"})
        result = self.simple_webhook.execute(raise_on_error=False)
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("Webhook boom!", result["message"])

    def test_webhook_code_returns_non_dict(self):
        """
        Test that webhook fails gracefully if code returns non-dict
        """
        self.simple_webhook.write({"code": "result = 'not a dict'"})
        result = self.simple_webhook.execute(raise_on_error=False)
        self.assertEqual(result["exit_code"], 1)
        self.assertEqual(
            result["message"], "Webhook/Authenticator code error: result is not a dict"
        )

    def test_webhook_execute_raises_exception(self):
        """
        Test that webhook raises ValidationError if raise_on_error is True
        """
        self.simple_webhook.write({"code": "raise Exception('Validation failed!')"})
        with self.assertRaises(ValidationError):
            self.simple_webhook.execute(raise_on_error=True)

    def test_webhook_execute_with_payload(self):
        """
        Test that webhook receives and processes payload correctly
        """
        self.simple_webhook.write(
            {
                "code": "result = {'exit_code': 0, 'message': str(payload.get('key', 'none'))}"  # noqa: E501
            }
        )
        payload = {"key": "value123"}
        result = self.simple_webhook.execute(payload=payload, raise_on_error=False)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["message"], "value123")

    def test_webhook_execute_with_user(self):
        """
        Test that webhook executes as specified user
        """
        test_user = self.env.ref("base.user_demo")
        self.simple_webhook.user_id = test_user
        self.simple_webhook.write(
            {"code": "result = {'exit_code': 0, 'message': user.login}"}
        )
        result = self.simple_webhook.execute(raise_on_error=False)
        self.assertEqual(result["message"], test_user.login)

    def test_webhook_context_isolation(self):
        """
        Test that only payload is available in eval context;
        extra kwargs are not accessible
        """
        self.simple_webhook.write(
            {
                "code": (
                    "fail = []\n"
                    "for var in ['headers', 'raw_data', 'custom_param']:\n"
                    "    try:\n"
                    "        _ = eval(var)\n"
                    "        fail.append(var)\n"
                    "    except Exception:\n"
                    "        pass\n"
                    "if fail:\n"
                    "    result = {'exit_code': 99, 'message': 'Leaked vars: ' + ','.join(fail)}\n"  # noqa: E501
                    "else:\n"
                    "    result = {'exit_code': 0, 'message': 'Context clean'}\n"
                )
            }
        )
        result = self.simple_webhook.execute(
            payload={"key": "val"},
            headers={"x": "y"},
            raw_data="boom",
            custom_param="xxx",
            raise_on_error=False,
        )
        self.assertEqual(result["exit_code"], 0, result["message"])
        self.assertIn("Context clean", result["message"])

    def test_webhook_execute_runs_as_user_id(self):
        """
        Test that the webhook code is always executed as the specified user_id,
        regardless of the caller's user context or extra kwargs.
        """
        # set specific user
        test_user = self.env.ref("base.user_demo")
        self.simple_webhook.user_id = test_user
        self.simple_webhook.write(
            {"code": "result = {'exit_code': 0, 'message': user.login}"}
        )

        # run execute() with another user and try to pass user_id via kwargs
        other_user = self.env.ref("base.user_admin")
        result = self.simple_webhook.with_user(other_user).execute(
            payload={},
            user_id=self.env.ref("base.user_root").id,  # try to pass own user_id
            raise_on_error=False,
        )
        # the result should be from user_demo anyway
        self.assertEqual(result["message"], test_user.login)
