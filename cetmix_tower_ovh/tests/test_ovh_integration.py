# Copyright 2024 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo.tests import common


class TestOvhIntegration(common.TransactionCase):
    """Test OVH integration with Cetmix Tower commands."""

    def setUp(self):
        super().setUp()
        # Create a test command
        self.command = self.env["cx.tower.command"].create(
            {
                "name": "Test OVH Command",
                "action": "python_code",
            }
        )
        self.eval_context = self.env[
            "cx.tower.command"
        ]._get_python_command_eval_context()

    def test_ovh_in_evaluation_context(self):
        """Test that ovh is added to the evaluation context."""
        self.assertIn("ovh", self.eval_context)
        ovh_obj = self.eval_context["ovh"]
        self.assertTrue(hasattr(ovh_obj, "Client"))

    def test_ovh_in_evaluation_context_with_server(self):
        """Test that ovh is added to the evaluation context when server is provided."""
        test_server = self.env["cx.tower.server"].create(
            {
                "name": "Test OVH Server",
                "reference": "test_ovh_server",
                "ip_v4_address": "localhost",
                "ssh_username": "admin",
                "ssh_password": "password",
                "ssh_auth_mode": "p",
                "host_key": "test_key",
            }
        )
        eval_context = self.env["cx.tower.command"]._get_python_command_eval_context(
            server=test_server
        )

        self.assertIn("ovh", eval_context)
        ovh_obj = eval_context["ovh"]
        self.assertTrue(hasattr(ovh_obj, "Client"))
        self.assertEqual(eval_context["server"], test_server)

    def test_ovh_client_instantiation(self):
        """Test that ovh.Client can be instantiated from context."""
        ovh_mod = self.eval_context["ovh"]
        # Only test instantiation, do not require credentials
        try:
            client = ovh_mod.Client(
                endpoint="ovh-eu",
                application_key="a",
                application_secret="b",
                consumer_key="c",
            )
            self.assertIsNotNone(client)
        except Exception as e:
            self.fail(f"ovh.Client instantiation failed: {e}")
