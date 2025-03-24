# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from unittest.mock import patch

from ..models.constants import GENERAL_ERROR, NOT_FOUND, SSH_CONNECTION_ERROR
from .common import TestTowerCommon


class TestCetmixTower(TestTowerCommon):
    """
    Tests for the 'cetmix.tower' helper model
    """

    def test_server_set_variable_value(self):
        """Test plan line action naming"""

        # -- 1--
        # Create new variable
        variable_meme = self.Variable.create(
            {"name": "Meme Variable", "reference": "meme_variable"}
        )

        # Set variable for Server 1
        result = self.CetmixTower.server_set_variable_value(
            server_reference=self.server_test_1.reference,
            variable_reference=variable_meme.reference,
            value="Doge",
        )

        # Check exit code
        self.assertEqual(result["exit_code"], 0, "Exit code must be equal to 0")

        # Check variable value
        variable_value = self.VariableValue.search(
            [("variable_id", "=", variable_meme.id)]
        )

        self.assertEqual(len(variable_value), 1, "Must be 1 result")
        self.assertEqual(variable_value.value_char, "Doge", "Must be Doge!")

        # -- 2 --
        # Update existing variable value

        # Set variable for Server 1
        result = self.CetmixTower.server_set_variable_value(
            server_reference=self.server_test_1.reference,
            variable_reference=variable_meme.reference,
            value="Pepe",
        )

        # Check exit code
        self.assertEqual(result["exit_code"], 0, "Exit code must be equal to 0")

        # Check variable value
        variable_value = self.VariableValue.search(
            [("variable_id", "=", variable_meme.id)]
        )

        self.assertEqual(len(variable_value), 1, "Must be 1 result")
        self.assertEqual(variable_value.value_char, "Pepe", "Must be Pepe!")

    def test_server_get_variable_value(self):
        """Test getting value for server"""
        variable_meme = self.Variable.create(
            {"name": "Meme Variable", "reference": "meme_variable"}
        )
        global_value = self.VariableValue.create(
            {"variable_id": variable_meme.id, "value_char": "Memes Globalvs"}
        )

        # -- 1 -- Get value for Server with no server value defined
        value = self.CetmixTower.server_get_variable_value(
            self.server_test_1.reference, variable_meme.reference
        )
        self.assertEqual(value, global_value.value_char)

        # -- 2 -- Do not fetch global value now
        value = self.CetmixTower.server_get_variable_value(
            self.server_test_1.reference, variable_meme.reference, check_global=False
        )
        self.assertIsNone(value)

        # -- 3 -- Add server value and try again
        server_value = self.VariableValue.create(
            {
                "variable_id": variable_meme.id,
                "value_char": "Memes Servervs",
                "server_id": self.server_test_1.id,
            }
        )
        value = self.CetmixTower.server_get_variable_value(
            self.server_test_1.reference, variable_meme.reference
        )
        self.assertEqual(value, server_value.value_char)

    def test_server_check_ssh_connection(self):
        """
        Test SSH connection check with a mocked function that
        either returns a dictionary or raises an exception.
        """

        # Test successful connection
        result = self.env["cetmix.tower"].server_check_ssh_connection(
            self.server_test_1.reference,
        )
        self.assertEqual(result["exit_code"], 0, "SSH connection should be successful.")

        def test_ssh_connection(this, *args, **kwargs):
            return {"status": GENERAL_ERROR}

        with patch.object(
            self.registry["cx.tower.server"], "test_ssh_connection", test_ssh_connection
        ):
            # Test connection timeout after max attempts
            result = self.env["cetmix.tower"].server_check_ssh_connection(
                self.server_test_1.reference,
                attempts=2,
                wait_time=1,
            )
            self.assertEqual(
                result["exit_code"],
                SSH_CONNECTION_ERROR,
                "SSH connection should timeout after maximum attempts.",
            )

    def test_server_run_command(self):
        """Test running command on server"""
        # Create test command
        command = self.Command.create(
            {
                "name": "Test Command",
                "reference": "test_command",
                "code": "echo 'Hello World'",
                "action": "ssh_command",
            }
        )

        # -- 1 -- Test with non-existent server
        result = self.CetmixTower.server_run_command(
            server_reference="non_existent",
            command_reference=command.reference,
        )
        self.assertEqual(result["exit_code"], NOT_FOUND)
        self.assertEqual(result["message"], "Server not found")

        # -- 2 -- Test with non-existent command
        result = self.CetmixTower.server_run_command(
            server_reference=self.server_test_1.reference,
            command_reference="non_existent",
        )
        self.assertEqual(result["exit_code"], NOT_FOUND)
        self.assertEqual(result["message"], "Command not found")

        # -- 3 -- Test successful command execution
        result = self.CetmixTower.server_run_command(
            server_reference=self.server_test_1.reference,
            command_reference=command.reference,
        )
        self.assertEqual(result["exit_code"], 0)

    def test_server_run_flight_plan(self):
        """Test running flight plan on server"""
        # Create test flight plan
        flight_plan = self.Plan.create(
            {
                "name": "Test Flight Plan",
                "reference": "test_flight_plan",
            }
        )

        # -- 1 -- Test with non-existent server
        result = self.CetmixTower.server_run_flight_plan(
            server_reference="non_existent",
            flight_plan_reference=flight_plan.reference,
        )
        self.assertFalse(result, "Should return False for non-existent server")

        # -- 2 -- Test with non-existent flight plan
        result = self.CetmixTower.server_run_flight_plan(
            server_reference=self.server_test_1.reference,
            flight_plan_reference="non_existent",
        )
        self.assertFalse(result, "Should return False for non-existent flight plan")

        # -- 3 -- Test successful flight plan execution
        with patch.object(self.server_test_1.__class__, "run_flight_plan") as mock_run:
            # Setup mock to return a plan log record
            plan_log = self.PlanLog.create(
                {
                    "name": "Test Log",
                    "server_id": self.server_test_1.id,
                    "plan_id": flight_plan.id,
                }
            )
            mock_run.return_value = plan_log

            # Run flight plan
            result = self.CetmixTower.server_run_flight_plan(
                server_reference=self.server_test_1.reference,
                flight_plan_reference=flight_plan.reference,
            )

            # Verify result
            self.assertEqual(result, plan_log, "Should return plan log record")
            mock_run.assert_called_once_with(flight_plan)
