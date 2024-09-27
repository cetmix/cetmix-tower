# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

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
        variable_value = self.VariableValues.search(
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
        variable_value = self.VariableValues.search(
            [("variable_id", "=", variable_meme.id)]
        )

        self.assertEqual(len(variable_value), 1, "Must be 1 result")
        self.assertEqual(variable_value.value_char, "Pepe", "Must be Pepe!")
