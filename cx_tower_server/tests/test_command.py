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
