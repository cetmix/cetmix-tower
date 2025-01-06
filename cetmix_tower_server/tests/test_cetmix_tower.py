# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from unittest.mock import patch

from ..models.constants import SSH_CONNECTION_ERROR, SSH_CONNECTION_TIMEOUT
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

        def mock_server_check_ssh_connection(
            this, server_reference, attempts=5, timeout=15
        ):
            if server_reference == self.server_test_1.reference:
                return {
                    "code": 0,
                    "message": "Mocked: SSH connection successful",
                }
            elif server_reference == "invalid_server":
                raise ValueError("Mocked: Invalid server reference")
            elif server_reference == "timeout_server":
                raise TimeoutError("Mocked: SSH connection timed out")
            elif server_reference == "max_attempts_timeout":
                return {
                    "code": SSH_CONNECTION_TIMEOUT,
                    "message": "Mocked: SSH connection timeout on last attempt",
                }
            else:
                return {
                    "code": SSH_CONNECTION_ERROR,
                    "message": "Mocked: Unknown server",
                }

        with patch(
            "odoo.addons.cetmix_tower_server.models.cetmix_tower.CetmixTower.server_check_ssh_connection",
            mock_server_check_ssh_connection,
        ):
            # Test successful connection
            result = self.env["cetmix.tower"].server_check_ssh_connection(
                self.server_test_1.reference
            )
            self.assertEqual(result["code"], 0, "SSH connection should be successful.")

            # Test invalid server
            with self.assertRaises(ValueError):
                self.env["cetmix.tower"].server_check_ssh_connection("invalid_server")

            # Test connection timeout
            with self.assertRaises(TimeoutError):
                self.env["cetmix.tower"].server_check_ssh_connection("timeout_server")

            # Test connection timeout after max attempts
            result = self.env["cetmix.tower"].server_check_ssh_connection(
                "max_attempts_timeout", attempts=5
            )
            self.assertEqual(
                result["code"],
                SSH_CONNECTION_TIMEOUT,
                "SSH connection should timeout after maximum attempts.",
            )

            # Test unknown server
            result = self.env["cetmix.tower"].server_check_ssh_connection(
                "unknown_server"
            )
            self.assertEqual(
                result["code"],
                SSH_CONNECTION_ERROR,
                "Unknown server should return code 503.",
            )
