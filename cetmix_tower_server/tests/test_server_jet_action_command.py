# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from odoo import _
from odoo.exceptions import ValidationError

from odoo.addons.cetmix_tower_server.models.constants import (
    GENERAL_ERROR,
    JET_NOT_FOUND,
    JET_TEMPLATE_NOT_FOUND,
)

from .common_jets import TestTowerJetsCommon


class TestTowerServerJetActionCommand(TestTowerJetsCommon):  # pylint: disable=protected-access
    """Tests for cx.tower.server._command_runner_jet_action."""

    def _create_jet_action_command(self, jet_template, jet_action):
        """Create a command that triggers a jet action for the given template."""
        return self.Command.create(
            {
                "name": "Test jet action command",
                "action": "jet_action",
                "jet_template_id": jet_template.id,
                "jet_action_id": jet_action.id,
            }
        )

    def _create_jet_action_log(self, jet, command):
        """Create a command log bound to a jet and command."""
        return self.CommandLog.create(
            {
                "server_id": jet.server_id.id,
                "command_id": command.id,
                "jet_id": jet.id,
            }
        )

    def test_command_runner_jet_action_requires_log_record(self):
        """Calling without a log record must raise ValidationError."""
        with self.assertRaises(ValidationError):
            self.server_test_1._command_runner_jet_action(False)

    def test_command_runner_jet_action_missing_jet_action(self):
        """Missing command jet_action_id finishes with GENERAL_ERROR."""
        command = self._create_jet_action_command(
            self.jet_template_test,
            self.action_stopped_to_running,
        )
        command.write({"jet_action_id": False})
        log = self._create_jet_action_log(self.jet_test, command)

        result = self.server_test_1._command_runner_jet_action(log)

        self.assertEqual(result["status"], GENERAL_ERROR)
        self.assertEqual(result["response"], None)
        self.assertEqual(result["error"], _("Jet action is not found."))
        log.invalidate_recordset()
        self.assertEqual(log.command_status, GENERAL_ERROR)

    def test_command_runner_jet_action_missing_jet(self):
        """Missing jet on the log finishes with JET_NOT_FOUND."""
        command = self._create_jet_action_command(
            self.jet_template_test,
            self.action_stopped_to_running,
        )
        log = self.CommandLog.create(
            {
                "server_id": self.server_test_1.id,
                "command_id": command.id,
                "jet_id": False,
            }
        )

        result = self.server_test_1._command_runner_jet_action(log)

        self.assertEqual(result["status"], JET_NOT_FOUND)
        self.assertIsNotNone(result["error"])

    def test_command_runner_jet_action_missing_jet_template(self):
        """
        Missing jet_template_id on the command finishes with
        JET_TEMPLATE_NOT_FOUND.
        """
        command = self._create_jet_action_command(
            self.jet_template_test,
            self.action_stopped_to_running,
        )
        command.write({"jet_template_id": False})
        log = self._create_jet_action_log(self.jet_test, command)

        result = self.server_test_1._command_runner_jet_action(log)

        self.assertEqual(result["status"], JET_TEMPLATE_NOT_FOUND)
        self.assertIsNotNone(result["error"])

    @patch(
        "odoo.addons.cetmix_tower_server.models.cx_tower_jet.CxTowerJet._trigger_action",
        autospec=True,
    )
    def test_command_runner_jet_action_success_aggregates_response(self, mock_trigger):
        mock_trigger.return_value = {"status": 0, "error": None}
        command = self._create_jet_action_command(
            self.jet_template_test,
            self.action_stopped_to_running,
        )
        log = self._create_jet_action_log(self.jet_test, command)

        result = self.server_test_1._command_runner_jet_action(log)

        self.assertEqual(result["status"], 0)
        self.assertIsNone(result["error"])
        self.assertTrue(result["response"])
        self.assertIn("Action triggered for", result["response"])
        self.assertIn(self.jet_test.reference, result["response"])
        mock_trigger.assert_called_once()
        log.invalidate_recordset()
        self.assertEqual(log.command_status, 0)
        self.assertIn("Action triggered for", log.command_response)
        self.assertFalse(log.command_error)

    @patch(
        "odoo.addons.cetmix_tower_server.models.cx_tower_jet.CxTowerJet._trigger_action",
        autospec=True,
    )
    def test_command_runner_jet_action_failure_single_jet_error_message(
        self, mock_trigger
    ):
        mock_trigger.return_value = {"status": 1, "error": "No action found"}
        command = self._create_jet_action_command(
            self.jet_template_test,
            self.action_stopped_to_running,
        )
        log = self._create_jet_action_log(self.jet_test, command)

        result = self.server_test_1._command_runner_jet_action(log)

        self.assertEqual(result["status"], GENERAL_ERROR)
        self.assertIsNone(result["response"])
        self.assertTrue(result["error"])
        lines = result["error"].split("\n")
        self.assertEqual(len(lines), 2)
        self.assertIn("Action triggered for", lines[0])
        self.assertIn(self.jet_test.reference, lines[1])
        self.assertIn("No action found", lines[1])

    @patch(
        "odoo.addons.cetmix_tower_server.models.cx_tower_jet.CxTowerJet._trigger_action",
        autospec=True,
    )
    def test_command_runner_jet_action_failure_status_without_error_text(
        self, mock_trigger
    ):
        mock_trigger.return_value = {"status": 99, "error": None}
        command = self._create_jet_action_command(
            self.jet_template_test,
            self.action_stopped_to_running,
        )
        log = self._create_jet_action_log(self.jet_test, command)

        result = self.server_test_1._command_runner_jet_action(log)

        self.assertEqual(result["status"], GENERAL_ERROR)
        self.assertIn(self.jet_test.reference, result["error"])
        self.assertIn("99", result["error"])

    @patch(
        "odoo.addons.cetmix_tower_server.models.cx_tower_jet.CxTowerJet._trigger_action",
        autospec=True,
    )
    def test_command_runner_jet_action_failure_multiple_jets(self, mock_trigger):
        jet_b = self._create_jet(
            name="Second Jet",
            reference="jet_second",
            template=self.jet_template_test,
            server=self.server_test_1,
        )

        def side_effect(jet_self, *_args, **_kwargs):
            jet_self.ensure_one()
            if jet_self.id == self.jet_test.id:
                return {"status": 1, "error": "No action found"}
            return {"status": 2, "error": "Jet is busy"}

        mock_trigger.side_effect = side_effect

        command = self._create_jet_action_command(
            self.jet_template_test,
            self.action_stopped_to_running,
        )
        log = self._create_jet_action_log(self.jet_woocommerce, command)

        with patch(
            "odoo.addons.cetmix_tower_server.models.cx_tower_jet.CxTowerJet._get_dependent_jets_by_template",
            autospec=True,
            return_value=self.jet_test | jet_b,
        ):
            result = self.server_test_1._command_runner_jet_action(log)

        self.assertEqual(result["status"], GENERAL_ERROR)
        lines = result["error"].split("\n")
        self.assertEqual(len(lines), 2)
        self.assertIn("Action triggered for", lines[0])
        self.assertIn(self.jet_test.reference, lines[0])
        self.assertIn(jet_b.reference, lines[0])
        agg = lines[1]
        self.assertIn(f"{self.jet_test.reference}: No action found", agg)
        self.assertIn(f"{jet_b.reference}: Jet is busy", agg)

    @patch(
        "odoo.addons.cetmix_tower_server.models.cx_tower_jet.CxTowerJet._get_dependent_jets_by_template",
        autospec=True,
    )
    def test_command_runner_jet_action_no_dependent_jets(self, mock_deps):
        mock_deps.return_value = self.Jet.browse()
        command = self._create_jet_action_command(
            self.jet_template_test,
            self.action_stopped_to_running,
        )
        log = self._create_jet_action_log(self.jet_woocommerce, command)

        result = self.server_test_1._command_runner_jet_action(log)

        self.assertEqual(result["status"], 0)
        self.assertIsNone(result["error"])
        self.assertTrue(result["response"])
        self.assertIn(self.jet_woocommerce.name, result["response"])
        self.assertIn(self.jet_template_test.name, result["response"])
