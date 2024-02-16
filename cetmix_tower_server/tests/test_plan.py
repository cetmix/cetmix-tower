# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, fields

from .test_common import TestTowerCommon


class TestTowerPlan(TestTowerCommon):
    def test_plan_line_action_name(self):
        """Test plan line action naming"""

        # Add new line
        plan_line_1 = self.plan_line.create(
            {
                "plan_id": self.plan_1.id,
                "command_id": self.command_create_dir.id,
                "sequence": 10,
            }
        )

        # Add new action with custom
        action_1 = self.plan_line_action.create(
            {
                "line_id": plan_line_1.id,
                "condition": "==",
                "value_char": "35",
                "action": "e",
            }
        )

        # Check if action name is composed correctly
        expected_action_string = _(
            "If exit code == 35 then Exit with command exit code"
        )
        self.assertEqual(
            action_1.name,
            expected_action_string,
            msg="Action name doesn't match expected one",
        )

    def test_plan_get_next_action_values(self):
        """Test _get_next_action_values()

        NB: This test relies on demo data and might fail if it is modified
        """

        # Ensure demo date integrity just in case demo date is modified
        self.assertEqual(
            self.plan_1.line_ids[0].action_ids[1].custom_exit_code,
            255,
            "Plan 1 line #1 action #2 custom exit code must be equal to 255",
        )

        # Create a new plan log.
        plan_line_1 = self.plan_1.line_ids[0]  # Using command 1 from Plan 1
        plan_log = self.PlanLog.create(
            {
                "server_id": self.server_test_1.id,
                "plan_id": self.plan_1.id,
                "is_running": True,
                "start_date": fields.Datetime.now(),
                "plan_line_executed_id": plan_line_1.id,
            }
        )

        # ************************
        # Test with exit code == 0
        # Must run the next command
        # ************************
        command_log = self.CommandLog.create(
            {
                "plan_log_id": plan_log.id,
                "server_id": self.server_test_1.id,
                "command_id": plan_line_1.command_id.id,
                "command_response": "Ok",
                "command_status": 0,  # Error code
            }
        )
        action, exit_code, next_line_id = self.plan_1._get_next_action_values(
            command_log
        )
        self.assertEqual(action, "n", msg="Action must be 'Execute next action'")
        self.assertEqual(exit_code, 0, msg="Exit code must be equal to 0")
        self.assertEqual(
            next_line_id,
            self.env.ref("cetmix_tower_server.plan_test_1_line_2"),
            msg="Next line must be Line #2",
        )

        # ************************
        # Test with exit code == 8
        # Must exit with custom code
        # ************************
        command_log.command_status = 8

        action, exit_code, next_line_id = self.plan_1._get_next_action_values(
            command_log
        )
        self.assertEqual(action, "ec", msg="Action must be 'Exit with custom code'")
        self.assertEqual(exit_code, 255, msg="Exit code must be equal to 255")
        self.assertIsNone(next_line_id, msg="Next line must be None")

        # ************************
        # Test with exit code == -12
        # Plan on error action must be triggered because no action condition is matched
        # ************************
        command_log.command_status = -12

        action, exit_code, next_line_id = self.plan_1._get_next_action_values(
            command_log
        )
        self.assertEqual(action, "e", msg="Action must be 'Exit with command code'")
        self.assertEqual(exit_code, -12, msg="Exit code must be equal to -12")
        self.assertIsNone(next_line_id, msg="Next line must be None")

        # ************************
        # Change Plan 'On error action' of the plan to 'Run next command'
        # Next line must be Line #2
        # ************************

        command_log.command_status = -12
        self.plan_1.on_error_action = "n"

        action, exit_code, next_line_id = self.plan_1._get_next_action_values(
            command_log
        )
        self.assertEqual(action, "n", msg="Action must be 'Execute next action'")
        self.assertEqual(exit_code, -12, msg="Exit code must be equal to -12")
        self.assertEqual(
            next_line_id,
            self.env.ref("cetmix_tower_server.plan_test_1_line_2"),
            msg="Next line must be Line #2",
        )

        # ************************
        # Run Line 2 (the last one).
        # Action 2 will be triggered which is "Run next line".
        # However because this is the last line of the plan must exit with command code.
        # ************************

        plan_line_2 = self.plan_1.line_ids[1]
        plan_log.plan_line_executed_id = plan_line_2.id
        command_log.command_status = 3

        action, exit_code, next_line_id = self.plan_1._get_next_action_values(
            command_log
        )
        self.assertEqual(action, "e", msg="Action must be 'Exit with command code'")
        self.assertEqual(exit_code, 3, msg="Exit code must be equal to 3")
        self.assertIsNone(next_line_id, msg="Next line must be None")

        # ************************
        # Run Line 2 (the last one).
        # Fallback plan action must be triggered because no action condition is matched
        # However because this is the last line of the plan must exit with command code.
        # ************************

        command_log.command_status = 1

        action, exit_code, next_line_id = self.plan_1._get_next_action_values(
            command_log
        )
        self.assertEqual(action, "e", msg="Action must be 'Exit with command code'")
        self.assertEqual(exit_code, 1, msg="Exit code must be equal to 1")
        self.assertIsNone(next_line_id, msg="Next line must be None")

    def test_plan_execute_single(self):
        """Test plan execution results"""

        # Execute plan
        self.plan_1._execute_single(self.server_test_1)

        # Check plan log
        plan_log_rec = self.PlanLog.search([])

        # Must be a single record
        self.assertEqual(len(plan_log_rec), 1, msg="Must be a single plan record")

        # Ensure all commands were triggered
        expected_command_count = 2
        self.assertEqual(
            len(plan_log_rec.command_log_ids),
            expected_command_count,
            msg="Must run {} commands".format(expected_command_count),
        )

        # Check plan status
        expected_plan_status = 0
        self.assertEqual(
            plan_log_rec.plan_status,
            expected_plan_status,
            msg="Plan status must be equal to {}".format(expected_plan_status),
        )

        # ************************
        # Change condition in line #1.
        # Action 1 will be triggered which is "Exit with custom code" 29.
        # ************************
        action_to_tweak = self.env.ref(
            "cetmix_tower_server.plan_test_1_line_1_action_1"
        )
        action_to_tweak.write({"custom_exit_code": 29, "action": "ec"})

        # Execute plan
        self.plan_1._execute_single(self.server_test_1)

        # Check plan log
        plan_log_records = self.PlanLog.search([])

        # Must be two plan log record
        self.assertEqual(len(plan_log_records), 2, msg="Must be 2 plan log records")
        plan_log_rec = plan_log_records[0]

        # Ensure all commands were triggered
        expected_command_count = 1
        self.assertEqual(
            len(plan_log_rec.command_log_ids),
            expected_command_count,
            msg="Must run {} commands".format(expected_command_count),
        )

        # Check plan status
        expected_plan_status = 29
        self.assertEqual(
            plan_log_rec.plan_status,
            expected_plan_status,
            msg="Plan status must be equal to {}".format(expected_plan_status),
        )
