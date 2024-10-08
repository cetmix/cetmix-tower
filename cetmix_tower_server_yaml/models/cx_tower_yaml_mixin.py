# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import yaml

from odoo import fields, models


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

    yaml_code = fields.Text(compute="_compute_yaml_code")

    def _compute_yaml_code(self):
        """Compute YAML code based on model record data"""
        for record in self:
            # We are reading field list for each record
            # because list of fields can differ from record to record
            yaml_keys = record._get_fields_for_yaml()
            record_dict = record.read(fields=yaml_keys)[0]
            record.yaml_code = yaml.dump(
                self._post_process_record_values(record_dict),
                Dumper=CustomDumper,
                default_flow_style=False,
            )

    def _get_fields_for_yaml(self):
        """Get ist of field to be present in YAML

        Returns:
            list(): list of fields to be used as YAML keys
        """
        self.ensure_one()
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

        # Add YAML format version
        values.update({"cetmix_tower_yaml_version": self.CETMIX_TOWER_YAML_VERSION})

        # Parse access level
        if "access_level" in values:
            values.update(
                {"access_level": self.TO_YAML_ACCESS_LEVEL[values["access_level"]]}
            )
        return values
