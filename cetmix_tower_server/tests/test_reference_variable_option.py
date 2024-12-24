# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from .common import TestTowerCommon


class TestReferencesVariableOption(TestTowerCommon):
    def setUp(self):
        """
        Set up test data.
        """
        super().setUp()
        self.variable = self.env["cx.tower.variable"].create(
            {
                "name": "Odoo test",
                "reference": "odoo_test",
            }
        )

    def test_compute_variable_option_reference(self):
        """
        Test that the 'variable_option_reference' field is correctly computed.
        """
        variable_option = self.env["cx.tower.reference.variable.option"].create(
            {
                "variable_id": self.variable.id,
                "option": "16.0",
            }
        )
        expected_reference = "odoo_test_option_160"
        self.assertEqual(
            variable_option.variable_option_reference,
            expected_reference,
            "The computed 'variable_option_reference' is incorrect.",
        )
