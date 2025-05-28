# Copyright 2024 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo.tests import common

from ..models.constants import OVH_HELP_TEXT


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

    def test_ovh_in_evaluation_context(self):
        """Test that ovh is added to the evaluation context."""
        eval_context = self.env["cx.tower.command"]._get_eval_context()
        self.assertIn("ovh", eval_context)
        ovh_obj = eval_context["ovh"]
        self.assertTrue(hasattr(ovh_obj, "Client"))

    def test_ovh_in_python_code(self):
        """Test that OVH documentation is added to Python code commands."""
        self.assertIn(OVH_HELP_TEXT, self.command.code)

    def test_no_duplication_on_writes(self):
        """Test that OVH documentation is not duplicated on repeated writes."""
        self.command.write({"name": "Updated Test OVH Command"})
        occurrences = self.command.code.count(OVH_HELP_TEXT)
        self.assertEqual(occurrences, 1, "OVH help text should not be duplicated")

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
        eval_context = self.env["cx.tower.command"]._get_eval_context(
            server=test_server
        )
        self.assertIn("ovh", eval_context)
        ovh_obj = eval_context["ovh"]
        self.assertTrue(hasattr(ovh_obj, "Client"))
        self.assertEqual(eval_context["server"], test_server)

    def test_tldextract_in_evaluation_context(self):
        """Test that tldextract is added to the evaluation context."""
        eval_context = self.env["cx.tower.command"]._get_eval_context()
        self.assertIn("tldextract", eval_context)
        tldextract = eval_context["tldextract"]
        self.assertTrue(callable(getattr(tldextract, "extract", None)))

    def test_tldextract_extract_domain(self):
        """Test tldextract.extract returns correct domain parts."""
        eval_context = self.env["cx.tower.command"]._get_eval_context()
        tldextract = eval_context["tldextract"]
        result = tldextract.extract("https://sub.example.co.uk")
        self.assertEqual(result.domain, "example")
        self.assertEqual(result.suffix, "co.uk")
        self.assertEqual(result.subdomain, "sub")

    def test_ovh_and_tldextract_together(self):
        """Test both ovh and tldextract are present in the context."""
        eval_context = self.env["cx.tower.command"]._get_eval_context()
        self.assertIn("ovh", eval_context)
        self.assertIn("tldextract", eval_context)

    def test_tldextract_with_invalid_url(self):
        """Test tldextract.extract handles invalid URLs gracefully."""
        eval_context = self.env["cx.tower.command"]._get_eval_context()
        tldextract = eval_context["tldextract"]
        result = tldextract.extract("not_a_url")
        self.assertEqual(result.domain, "not_a_url")
        self.assertEqual(result.suffix, "")
        self.assertEqual(result.subdomain, "")

    def test_ovh_client_instantiation(self):
        """Test that ovh.Client can be instantiated from context."""
        eval_context = self.env["cx.tower.command"]._get_eval_context()
        ovh_mod = eval_context["ovh"]
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
