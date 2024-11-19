from odoo.tests import TransactionCase


class TestTowerServerTemplate(TransactionCase):
    def setUp(self, *args, **kwargs):
        super().setUp(*args, **kwargs)

        self.ServerTemplate = self.env["cx.tower.server.template"]

    def test_server_template_ssh_password_mask(self):
        """Test that SSH password is masked in YAML"""
        server_template = self.ServerTemplate.create(
            {"name": "Test Server Template", "ssh_password": "test_password"}
        )
        record_dict = server_template._prepare_record_for_yaml()
        self.assertEqual(
            record_dict["ssh_password"],
            self.ServerTemplate.SSH_PASSWORD_MASK,
            f"Expected {self.ServerTemplate.SSH_PASSWORD_MASK},"
            f" but got: {record_dict.get('ssh_password')}",
        )
