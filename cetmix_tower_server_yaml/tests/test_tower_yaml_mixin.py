from odoo import _
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase


class TestTowerYamlMixin(TransactionCase):
    def setUp(self, *args, **kwargs):
        super().setUp(*args, **kwargs)

        # Patch method to return "access_level" field too
        def _get_fields_for_yaml(self):
            return ["access_level", "name", "reference"]

        self.YamlMixin = self.env["cx.tower.yaml.mixin"]
        self.YamlMixin._patch_method("_get_fields_for_yaml", _get_fields_for_yaml)

    def tearDown(self):
        # Remove the monkey patches
        self.YamlMixin._revert_method("_get_fields_for_yaml")
        super(TestTowerYamlMixin, self).tearDown()

    def test_post_process_record_values(self):
        """Test value post processing.
        We test common fields only because this method can be overridden
        in models inheriting this mixin.
        """
        source_values = {
            "access_level": "3",
            "id": 22332,
            "name": "Doge Much Like",
            "reference": "such_much_doge",
        }

        result_values = self.YamlMixin._post_process_record_values(source_values.copy())

        self.assertNotIn("id", result_values, "ID must be removed")
        self.assertEqual(
            result_values["access_level"],
            self.YamlMixin.TO_YAML_ACCESS_LEVEL[source_values["access_level"]],
            "Access level is not parsed correctly",
        )
        self.assertEqual(
            result_values["cetmix_tower_yaml_version"],
            self.YamlMixin.CETMIX_TOWER_YAML_VERSION,
            "Cetmix Tower YAML version is not added",
        )
        self.assertEqual(
            result_values["name"],
            source_values["name"],
            "Other values should remain unchanged",
        )
        self.assertEqual(
            result_values["reference"],
            source_values["reference"],
            "Other values should remain unchanged",
        )

    def test_post_process_yaml_dict_values(self):
        """Test YAML dict value post processing.
        We test common fields only because this method can be overridden
        in models inheriting this mixin.
        """

        # -- 1 --
        # Test regular flow
        source_values = {
            "access_level": "user",
            "cetmix_tower_yaml_version": self.YamlMixin.CETMIX_TOWER_YAML_VERSION,
            "name": "Doge Much Like",
            "reference": "such_much_doge",
            "some_doge_field": "some_meme",
        }

        result_values = self.YamlMixin._post_process_yaml_dict_values(
            source_values.copy()
        )
        self.assertNotIn(
            "some_doge_field", result_values, "Non listed fields must be removed"
        )
        self.assertNotIn(
            "cetmix_tower_yaml_version",
            result_values,
            "Cetmix Tower YAML version must be removed",
        )
        self.assertEqual(
            result_values["access_level"],
            self.YamlMixin.TO_TOWER_ACCESS_LEVEL[source_values["access_level"]],
            "Access level is not parsed correctly",
        )
        self.assertEqual(
            result_values["name"],
            source_values["name"],
            "Other values should remain unchanged",
        )
        self.assertEqual(
            result_values["reference"],
            source_values["reference"],
            "Other values should remain unchanged",
        )

        # -- 2 --
        # Test flow with exception due to yaml version incompatibility
        source_values = {
            "access_level": "user",
            "cetmix_tower_yaml_version": self.YamlMixin.CETMIX_TOWER_YAML_VERSION + 1,
            "name": "Doge Much Like",
            "reference": "such_much_doge",
            "some_doge_field": "some_meme",
        }

        with self.assertRaises(ValidationError) as e:
            result_values = self.YamlMixin._post_process_yaml_dict_values(
                source_values.copy()
            )
            self.assertEqual(
                str(e),
                _(
                    "YAML version is higher than version"
                    " supported by your Cetmix Tower instance. %(code_version)s > %(tower_version)s",  # noqa
                    code_version=self.YamlMixin.CETMIX_TOWER_YAML_VERSION + 1,
                    tower_version=self.YamlMixin.CETMIX_TOWER_YAML_VERSION,
                ),
                "Exception message doesn't match",
            )

        # -- Test 3 --
        # Submit wrong value for access level
        source_values.update(
            {
                "access_level": "doge",
                "cetmix_tower_yaml_version": self.YamlMixin.CETMIX_TOWER_YAML_VERSION,
            }
        )
        with self.assertRaises(ValidationError) as e:
            result_values = self.YamlMixin._post_process_yaml_dict_values(
                source_values.copy()
            )
            self.assertEqual(
                str(e),
                _(
                    "Wrong value for 'access_level' key: %(acv)s",
                    acv="doge",
                ),
                "Exception message doesn't match",
            )
