from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase


class TestTowerKey(TransactionCase):
    def setUp(self, *args, **kwargs):
        super().setUp(*args, **kwargs)

        self.Key = self.env["cx.tower.key"]

    def test_key_secret_value_mask(self):
        """Test that secret value is masked in YAML"""
        key = self.Key.create(
            {"name": "Test Key", "key_type": "s", "secret_value": "test_secret"}
        )
        record_dict = key._prepare_record_for_yaml()
        self.assertEqual(record_dict["secret_value"], "********")

    def test_key_secret_value_mask_is_not_saved(self):
        """Test that secret value mask cannot be saved as a value"""

        # -- 1 --
        # Create a record with secret value mask as a value
        with self.assertRaises(ValidationError):
            self.Key.create(
                {
                    "name": "such much name",
                    "key_type": "s",
                    "reference": "test_key_secret_value_mask_is_not_saved",
                    "secret_value": self.Key.SECRET_VALUE_MASK,
                }
            )

        # -- 2 --
        # Create a record with a normal value
        my_nice_key = self.Key.create(
            {
                "name": "such much name",
                "key_type": "s",
                "secret_value": "my_nice_secret_value",
            }
        )

        self.assertEqual(my_nice_key.secret_value, "my_nice_secret_value")

        # -- 3 --
        # Update the record with secret value mask as a value
        with self.assertRaises(ValidationError):
            my_nice_key.write({"secret_value": self.Key.SECRET_VALUE_MASK})
