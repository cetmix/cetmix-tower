from odoo import _
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase


class TestTowerYamlMixin(TransactionCase):
    def setUp(self, *args, **kwargs):
        super().setUp(*args, **kwargs)
        self.YamlMixin = self.env["cx.tower.yaml.mixin"]

    def test_post_process_record_values(self):
        """Test value post processing.
        We test common fields only because this method can be overridden
        in models inheriting this mixin.
        """

        # Patch method to return "access_level" field too
        def _get_fields_for_yaml(self):
            return ["access_level", "name", "reference"]

        self.YamlMixin._patch_method("_get_fields_for_yaml", _get_fields_for_yaml)

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

        # Restore original method
        self.YamlMixin._revert_method("_get_fields_for_yaml")

    def test_post_process_yaml_dict_values(self):
        """Test YAML dict value post processing.
        We test common fields only because this method can be overridden
        in models inheriting this mixin.
        """

        # Patch method to return "access_level" field too
        def _get_fields_for_yaml(self):
            return ["access_level", "name", "reference"]

        self.YamlMixin._patch_method("_get_fields_for_yaml", _get_fields_for_yaml)

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

        # Restore original method
        self.YamlMixin._revert_method("_get_fields_for_yaml")

    def test_process_m2o_value_no_explode(self):
        """Test non exploded m2m values
        Non exploded values represent related record with reference only
        """

        # We are using command with file template for that
        file_template = self.env["cx.tower.file.template"].create(
            {"name": "Test m2o", "reference": "test_m2o"}
        )
        command = self.env["cx.tower.command"].create(
            {
                "name": "Command test m2o",
                "action": "file_using_template",
                "file_template_id": file_template.id,
            }
        )

        # -- 1 --
        # Record -> Yaml
        result = command._process_m2o_value(
            field="file_template_id",
            value=(command.file_template_id.id, command.file_template_id.name),
            record_mode=True,
        )
        self.assertEqual(
            result, file_template.reference, "Reference was not resolved correctly"
        )

        # -- 2 --
        # Yaml -> Record
        result = command._process_m2o_value(
            field="file_template_id", value=file_template.reference, record_mode=False
        )
        self.assertEqual(
            result, file_template.id, "Record ID was not resolved correctly"
        )

        # -- 3 --
        # Yaml with non existing reference -> Record
        result = command._process_m2o_value(
            field="file_template_id", value="such_much_not_reference", record_mode=False
        )
        self.assertFalse(result, "Must be an 'False'")

        # -- 4 --
        # No record -> Yaml
        result = command._process_m2o_value(
            field="file_template_id",
            value=self.env["cx.tower.file.template"],
            record_mode=True,
        )
        self.assertFalse(result, "Result must be 'False'")

    def test_process_m2o_value_explode(self):
        """Test exploded m2m values
        Exploded values represent related record with a child YAML structure
        """

        # We are using command with file template for that
        file_template = self.env["cx.tower.file.template"].create(
            {"name": "Test m2o", "reference": "test_m2o"}
        )
        file_template_values = file_template._prepare_record_for_yaml()
        command = (
            self.env["cx.tower.command"]
            .create(
                {
                    "name": "Command test m2o",
                    "action": "file_using_template",
                    "file_template_id": file_template.id,
                    "yaml_explode": True,  # This is not used
                }
            )
            .with_context(explode_related_record=True)
        )  # and this is the actual trigger

        # -- 1 --
        # Record -> Yaml
        result = command._process_m2o_value(
            field="file_template_id",
            value=(command.file_template_id.id, command.file_template_id.name),
            record_mode=True,
        )
        self.assertEqual(
            result, file_template_values, "Reference was not resolved correctly"
        )

        # -- 2 --
        # Yaml -> Record
        result = command._process_m2o_value(
            field="file_template_id", value=file_template_values, record_mode=False
        )
        self.assertEqual(
            result, file_template.id, "Record ID was not resolved correctly"
        )

        # -- 3 --
        # Yaml with non existing reference -> Record
        file_template_values.update(
            {
                "name": "Very new name",
                "reference": "such_much_not_reference",
                "source": "server",
                "file_type": "binary",
            }
        )
        result = command._process_m2o_value(
            field="file_template_id", value=file_template_values, record_mode=False
        )

        # New record must be created
        record = self.env["cx.tower.file.template"].browse(result)
        self.assertEqual(
            record.name, file_template_values["name"], "New record value doesn't match"
        )
        self.assertEqual(
            record.reference,
            file_template_values["reference"],
            "New record value doesn't match",
        )
        self.assertEqual(
            record.source,
            file_template_values["source"],
            "New record value doesn't match",
        )
        self.assertEqual(
            record.file_type,
            file_template_values["file_type"],
            "New record value doesn't match",
        )

        # -- 4 --
        # Yaml with no reference at all -> Record
        values_with_no_references = {
            "name": "Sorry no reference here",
            "source": "tower",
            "file_type": "binary",
        }
        result = command._process_m2o_value(
            field="file_template_id", value=values_with_no_references, record_mode=False
        )

        # New record must be created
        record = self.env["cx.tower.file.template"].browse(result)

        self.assertEqual(
            record.name,
            values_with_no_references["name"],
            "New record value doesn't match",
        )
        self.assertEqual(
            record.source,
            values_with_no_references["source"],
            "New record value doesn't match",
        )
        self.assertEqual(
            record.file_type,
            values_with_no_references["file_type"],
            "New record value doesn't match",
        )

        # -- 5 --
        # No record -> Yaml
        result = command._process_m2o_value(
            field="file_template_id",
            value=self.env["cx.tower.file.template"],
            record_mode=True,
        )
        self.assertFalse(result, "Result must be 'False'")
