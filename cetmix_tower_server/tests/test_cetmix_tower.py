# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from unittest.mock import patch

import paramiko

from odoo import _

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

    def test_server_check_ssh_connection_successful(self):
        """Test server SSH connection success."""
        with patch.object(paramiko.SSHClient, "connect") as mock_connect, patch.object(
            paramiko.SSHClient, "close"
        ) as mock_close:
            mock_connect.return_value = None
            mock_close.return_value = None

            result = self.env["cetmix.tower"].server_check_ssh_connection(
                server_reference=self.server_test_1.reference, attempts=3, timeout=10
            )

            # Check if the connection is successful
            self.assertEqual(result["code"], 0)
            self.assertEqual(result["message"], _("SSH connection successful"))
