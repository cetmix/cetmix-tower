# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import base64

import yaml

from odoo import _, fields, models
from odoo.exceptions import ValidationError


class CustomDumper(yaml.Dumper):
    """Custom dumper to ensures code
    is properly dumped in YAML
    """

    def represent_scalar(self, tag, value, style=None):
        if isinstance(value, str) and "\n" in value:
            style = "|"
        return super().represent_scalar(tag, value, style)


class CxTowerYamlMixin(models.AbstractModel):
    """Used to implement YAML rendering functions.
    Inherit in your model in case you want to YAML instance of the records.
    """

    _name = "cx.tower.yaml.mixin"
    _description = "Cetmix Tower YAML rendering mixin"

    # File format version in order to track compatibility
    CETMIX_TOWER_YAML_VERSION = 1

    # TO_YAML_* used to convert from Odoo field values to YAML
    TO_YAML_ACCESS_LEVEL = {"1": "user", "2": "manager", "3": "root"}

    # TO_TOWER_* used to convert from YAML field values to Tower ones
    TO_TOWER_ACCESS_LEVEL = {"user": "1", "manager": "2", "root": "3"}

    yaml_code = fields.Text(
        compute="_compute_yaml_code",
        inverse="_inverse_yaml_code",
    )
    yaml_file = fields.Binary(compute="_compute_yaml_code", attachment=False)
    yaml_file_name = fields.Char(compute="_compute_yaml_code")

    def _compute_yaml_code(self):
        """Compute YAML code based on model record data"""

        # This is used for the file name.
        # Eg cx.tower.command record will have 'command_' prefix.
        model_prefix = self._name.split(".")[-1]
        for record in self:
            # We are reading field list for each record
            # because list of fields can differ from record to record
            yaml_keys = record._get_fields_for_yaml()
            record_dict = record.read(fields=yaml_keys)[0]
            yaml_code = yaml.dump(
                record._post_process_record_values(record_dict),
                Dumper=CustomDumper,
                default_flow_style=False,
            )
            record.update(
                {
                    "yaml_code": yaml_code,
                    "yaml_file": base64.encodebytes(yaml_code.encode("utf-8")),
                    "yaml_file_name": f"{model_prefix}_{record.reference}.yaml",
                }
            )

    def _inverse_yaml_code(self):
        """Compose record based on provided YAML"""
        for record in self:
            if record.yaml_code:
                record_yaml_dict = yaml.safe_load(record.yaml_code)
                record_vals = record._post_process_yaml_dict_values(record_yaml_dict)
                record.update(record_vals)

    def _get_fields_for_yaml(self):
        """Get ist of field to be present in YAML

        Returns:
            list(): list of fields to be used as YAML keys
        """
        return ["name", "reference"]

    def _post_process_record_values(self, values):
        """Post process record values
            before converting them to YAML

        Args:
            values (dict): values returned by 'read' method

        Returns:
            dict(): processed values
        """
        # We don't need id because we are not using it
        values.pop("id")

        # Add YAML format version and model
        model_name = self._name.replace("cx.tower.", "").replace(".", "_")
        values.update(
            {
                "cetmix_tower_yaml_version": self.CETMIX_TOWER_YAML_VERSION,
                "cetmix_tower_model": model_name,
            }
        )

        # Parse access level
        if "access_level" in values:
            values.update(
                {"access_level": self.TO_YAML_ACCESS_LEVEL[values["access_level"]]}
            )
        return values

    def _post_process_yaml_dict_values(self, values):
        """Post process dictionary values generated from YAML code

        Args:
            values (dict): Dictionary generated from YAML

        Returns:
            dict(): Post-processed values
        """

        # Check Cetmix Tower YAML version
        yaml_version = values.pop("cetmix_tower_yaml_version")
        if (
            yaml_version
            and isinstance(yaml_version, int)
            and yaml_version > self.CETMIX_TOWER_YAML_VERSION
        ):
            raise ValidationError(
                _(
                    "YAML version is higher than version"
                    " supported by your Cetmix Tower instance. %(code_version)s > %(tower_version)s",  # noqa
                    code_version=yaml_version,
                    tower_version=self.CETMIX_TOWER_YAML_VERSION,
                )
            )

        # Remove model data
        # TODO: temp solution, use later for import
        if "cetmix_tower_model" in values:
            values.pop("cetmix_tower_model")

        # Parse access level
        if "access_level" in values:
            values_access_level = values["access_level"]
            access_level = self.TO_TOWER_ACCESS_LEVEL.get(values_access_level)
            if access_level:
                values.update({"access_level": access_level})
            else:
                raise ValidationError(
                    _(
                        "Wrong value for 'access_level' key: %(acv)s",
                        acv=values_access_level,
                    )
                )

        # Leave supported keys only
        supported_keys = self._get_fields_for_yaml()
        filtered_values = {k: v for k, v in values.items() if k in supported_keys}

        return filtered_values
