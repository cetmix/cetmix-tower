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
