from odoo.tests.common import Form

from .test_common import TestTowerCommon


class TestTowerCommand(TestTowerCommon):
    def test_render_code(self):
        """Test code template rendering"""

        # Only 'test_path' must be rendered
        args = {"test_path": "/tmp", "os": "debian"}
        res = self.command_create_dir.render_code(**args)
        rendered_code = res.get(self.command_create_dir.id)
        rendered_code_expected = "cd /tmp && mkdir "
        self.assertEqual(
            rendered_code,
            rendered_code_expected,
            msg="Must be rendered as '{}'".format(rendered_code_expected),
        )

        # 'test_path' and 'dir' must be rendered
        args = {"test_path": "/tmp", "os": "debian", "dir": "odoo"}
        res = self.command_create_dir.render_code(**args)
        rendered_code = res.get(self.command_create_dir.id)
        self.assertEqual(
            rendered_code,
            "cd /tmp && mkdir odoo",
            msg="Must be rendered as 'cd /tmp && mkdir odoo'",
        )

    def test_execute_commands(self):
        """Test code executing and command log records"""

        # Save variable values for Server 1
        with Form(self.server_test_1) as f:
            with f.variable_value_ids.new() as line:
                line.variable_id = self.variable_dir
                line.value_char = "test-odoo-1"
            with f.variable_value_ids.new() as line:
                line.variable_id = self.variable_path
                line.value_char = "/opt/tower"
            f.save()
        # cd None && mkdir /opt/odoo

        # Add label to track command log
        command_label = "Test Command #1"
        custom_values = {"log": {"label": command_label}}

        # Execute command for Server 1
        self.server_test_1.execute_commands(self.command_create_dir, **custom_values)

        # Expected rendered command code
        rendered_code_expected = "cd /opt/tower && mkdir test-odoo-1"

        # Get command log
        log_record = self.CommandLog.search([("label", "=", command_label)])

        # Check log values
        self.assertAlmostEqual(len(log_record), 1, msg="Must be a single log record")
        self.assertEqual(
            log_record.server_id.id,
            self.server_test_1.id,
            msg="Record must belong to Test 1",
        )
        self.assertEqual(
            log_record.command_id.id,
            self.command_create_dir.id,
            msg="Record must belong to command 'Create dir'",
        )
        self.assertEqual(
            log_record.code,
            rendered_code_expected,
            msg="Rendered code must be '{}'".format(rendered_code_expected),
        )
        self.assertNotEqual(
            log_record.command_status, 0, msg="Command status must not be equal to 0"
        )
