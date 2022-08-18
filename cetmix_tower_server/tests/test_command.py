from odoo.tests.common import Form

from .test_common import TestTowerCommon


class TestTowerCommand(TestTowerCommon):
    def test_render_code(self):
        """Test code template rendering"""

        args = {"path": "/tmp", "os": "debian"}
        res = self.command_create_dir.render_code(**args)
        rendered_code = res.get(self.command_create_dir.id)
        self.assertEqual(
            rendered_code,
            "cd /tmp && mkdir ",
            msg="Must be rendered as 'cd /tmp && mkdir '",
        )

        args = {"path": "/tmp", "os": "debian", "dir": "odoo"}
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
                line.value_char = "/opt/odoo"
            with f.variable_value_ids.new() as line:
                line.variable_id = self.variable_path
                line.value_char = "http://example.com"
            f.save()

        # Execute command for Server 1
        self.server_test_1.execute_commands(self.command_create_dir)

        # Get command log
