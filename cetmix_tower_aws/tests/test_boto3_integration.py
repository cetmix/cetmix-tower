# Copyright 2024 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo.tests import common


class TestBoto3Integration(common.TransactionCase):
    """Test boto3 integration with Cetmix Tower commands."""

    def setUp(self):
        super().setUp()
        # Create a test command
        self.command = self.env["cx.tower.command"].create(
            {
                "name": "Test AWS Command",
                "action": "python_code",
            }
        )
        self.eval_context = self.env[
            "cx.tower.command"
        ]._get_python_command_eval_context()

    def test_boto3_in_evaluation_context(self):
        """Test that boto3 is added to the evaluation context."""
        # Get evaluation context
        # Check if boto3 is in the evaluation context
        self.assertIn("boto3", self.eval_context)
        # Check available methods
        boto3_obj = self.eval_context["boto3"]
        self.assertTrue(hasattr(boto3_obj, "client"))
        self.assertTrue(hasattr(boto3_obj, "resource"))
        self.assertTrue(hasattr(boto3_obj, "Session"))

    def test_boto3_in_evaluation_context_with_server(self):
        """Test that boto3 is added to the evaluation context
        when server is provided."""
        # Create a test server
        test_server = self.env["cx.tower.server"].create(
            {
                "name": "Test AWS Server",
                "reference": "test_aws_server",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "host_key": "test_key",
            }
        )

        # Get evaluation context with server
        eval_context = self.env["cx.tower.command"]._get_python_command_eval_context(
            server=test_server
        )

        # Check if boto3 is in the evaluation context
        self.assertIn("boto3", eval_context)

        # Check available methods
        boto3_obj = eval_context["boto3"]
        self.assertTrue(hasattr(boto3_obj, "client"))
        self.assertTrue(hasattr(boto3_obj, "resource"))
        self.assertTrue(hasattr(boto3_obj, "Session"))

        # Verify server is correctly passed to the context
        self.assertEqual(eval_context["server"], test_server)
