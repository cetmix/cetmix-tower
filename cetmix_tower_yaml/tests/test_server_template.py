from odoo.exceptions import ValidationError
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

    def test_server_template_ssh_password_mask_is_not_saved(self):
        """Test that secret value mask cannot be saved as a value"""

        # -- 1 --
        # Create a record with ssh key mask as a value
        with self.assertRaises(ValidationError):
            self.ServerTemplate.create(
                {
                    "name": "such much name",
                    "reference": "test_server_template_ssh_password_mask_is_not_saved",
                    "ssh_auth_mode": "p",
                    "ssh_password": self.ServerTemplate.SSH_PASSWORD_MASK,
                }
            )

        # -- 2 --
        # Create a record with a normal value
        my_nice_server_template = self.ServerTemplate.create(
            {
                "name": "such much name",
                "reference": "test_server_template_ssh_password_mask_is_not_saved",
                "ssh_auth_mode": "p",
                "ssh_password": "my_nice_ssh_password",
            }
        )

        self.assertEqual(my_nice_server_template.ssh_password, "my_nice_ssh_password")

        # -- 3 --
        # Update the record with secret value mask as a value
        with self.assertRaises(ValidationError):
            my_nice_server_template.write(
                {"ssh_password": self.ServerTemplate.SSH_PASSWORD_MASK}
            )
