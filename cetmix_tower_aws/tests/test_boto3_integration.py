# Copyright 2024 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo.tests import common

from ..models.constants import BOTO3_HELP_TEXT


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

    def test_boto3_in_evaluation_context(self):
        """Test that boto3 is added to the evaluation context."""
        # Get evaluation context
        eval_context = self.env["cx.tower.command"]._get_eval_context()
        # Check if boto3 is in the evaluation context
        self.assertIn("boto3", eval_context)
        # Check available methods
        boto3_obj = eval_context["boto3"]
        self.assertTrue(hasattr(boto3_obj, "client"))
        self.assertTrue(hasattr(boto3_obj, "resource"))
        self.assertTrue(hasattr(boto3_obj, "Session"))

    def test_boto3_in_python_code(self):
        """Test that boto3 documentation is added to Python code commands."""
        # Check if boto3 help text is in the code
        self.assertIn(BOTO3_HELP_TEXT, self.command.code)

    def test_no_duplication_on_writes(self):
        """Test that boto3 documentation is not duplicated on repeated writes."""
        # Update the command to trigger _compute_code again
        self.command.write({"name": "Updated Test AWS Command"})

        # Count occurrences of the entire boto3 help text in the code
        occurrences = self.command.code.count(BOTO3_HELP_TEXT)
        # Verify there's exactly one occurrence
        self.assertEqual(occurrences, 1, "Boto3 help text should not be duplicated")

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
        eval_context = self.env["cx.tower.command"]._get_eval_context(
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
