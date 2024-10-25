# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import base64

import yaml

from odoo import _, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import ormcache


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
    yaml_explode = fields.Boolean(
        string="Explode",
        help="Add entire related record data instead of just a reference",
    )

    def _compute_yaml_code(self):
        """Compute YAML code based on model record data"""

        # This is used for the file name.
        # Eg cx.tower.command record will have 'command_' prefix.
        model_prefix = self._name.split(".")[-1]
        for record in self:
            # We are reading field list for each record
            # because list of fields can differ from record to record
            yaml_code = yaml.dump(
                record._prepare_record_for_yaml(),
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

    def _prepare_record_for_yaml(self):
        """Reads and processes current record before converting it to YAML

        Returns:
            dict: values ready for YAML conversion
        """
        self.ensure_one()
        yaml_keys = self._get_fields_for_yaml()
        record_dict = self.read(fields=yaml_keys)[0]
        return self._post_process_record_values(record_dict)

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

        # Check if we need to return a record dict or just a reference
        # Use context value first, revert to the record setting if not defined
        explode_related_record = self._context.get("explode_related_record")
        if explode_related_record is None:
            explode_related_record = self.yaml_explode

        # Post process m2o and x2m fields
        for key, value in values.items():
            # IMPORTANT: Odoo naming patterns must be followed for related fields.
            # This is why we are checking for the field name ending here.
            # Further checks for the field type are done
            #  in _process_relation_field_value()
            if key.endswith("_id") or key.endswith("_ids"):
                processed_value = self.with_context(
                    explode_related_record=explode_related_record
                )._process_relation_field_value(key, value, record_mode=True)
                values.update({key: processed_value})

        return values

    def _post_process_yaml_dict_values(self, values):
        """Post process dictionary values generated from YAML code

        Args:
            values (dict): Dictionary generated from YAML

        Returns:
            dict(): Post-processed values
        """

        # Check Cetmix Tower YAML version
        yaml_version = values.pop("cetmix_tower_yaml_version", None)
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

        # Post process m2o fields
        for key, value in filtered_values.items():
            # IMPORTANT: Odoo naming patterns must be followed for related fields.
            # This is why we are checking for the field name ending here.
            # Further checks for the field type are done
            # in _process_relation_field_value()
            if key.endswith("_id") or key.endswith("_ids"):
                processed_value = self.with_context(
                    explode_related_record=True
                )._process_relation_field_value(key, value, record_mode=False)
                filtered_values.update({key: processed_value})

        return filtered_values

    @ormcache("model_name")
    def _model_supports_yaml(self, model_name):
        """Checks if model supports YAML import/export

        Args:
            model_name (Char): model name

        Returns:
            Bool: True if YAML is supported
        """
        model = self.env[model_name]

        return hasattr(model, "yaml_code")

    def _process_relation_field_value(self, field, value, record_mode=False):
        """Post process Many2many or Many2one value

        Args:
            field (Char): Field the value belongs to
            value (Char): Value to process
            record_mode (Bool): If True process value as a record value
                                else process value as a YAML value
            Context:
                explode_related_record: if set will return entire record dictionary
                    not just a reference
        Returns:
            dict() or Char: record dictionary if fetch_record else reference
        """
        # Step 1: Return False if the value is not set or the field is not found
        if not value:
            return False

        field_obj = self._fields.get(field)
        if not field_obj:
            return False

        # Step 2: Return False if the field type doesn't match
        # or comodel is not defined
        field_type = field_obj.type
        if field_type not in ["many2many", "many2one"] or not field_obj.comodel_name:
            return False

        comodel = self.env[field_obj.comodel_name]
        explode_related_record = self._context.get("explode_related_record")

        # Step 3: process value based on the field type
        if field_type == "many2one":
            return self._process_m2o_value(
                comodel, value, explode_related_record, record_mode
            )
        if field_type == "many2many":
            return self._process_x2m_values(
                comodel, value, explode_related_record, record_mode
            )

        # Step 4: fall back if field type is not supported
        return False

    def _process_m2o_value(
        self, comodel, value, explode_related_record, record_mode=False
    ):
        """Post process many2one value
        Args:
            comodel (BaseClass): Model the value belongs to
            value (Char): Value to process
            explode_related_record (Bool): If True return entire record dict
                instead of a reference
            record_mode (Bool): If True process value as a record value
                                else process value as a YAML value

        Returns:
            dict() or Char: record dictionary if fetch_record else reference
        """

        # -- (Record -> YAML)
        if record_mode:
            # Retrieve the record based on the ID provided in the value
            record = comodel.browse(value[0])

            # If the context specifies to explode the related record,
            # return its dictionary representation
            if explode_related_record:
                return record._prepare_record_for_yaml() if record else False

            # Otherwise, return just the reference (or False if record does not exist)
            return record.reference if record else False

        # -- (YAML -> Record)
        # Step 1: Process value in normal mode
        record = False

        # If the value is a string, it is treated as a reference
        if isinstance(value, str):
            reference = value

        # If the value is a dictionary, extract the reference from it
        elif isinstance(value, dict):
            reference = value.get("reference")
            record = self._update_or_create_related_record(comodel, reference, value)
        else:
            return False

        # Step 2: Final fallback: attempt to retrieve the record by reference if set,
        #  return its ID or False
        if not record and reference:
            record = comodel.get_by_reference(reference)
        return record.id if record else False

    def _process_x2m_values(
        self, comodel, values, explode_related_record, record_mode=False
    ):
        """Post process many2many value
        Args:
            comodel (BaseClass): Model the value belongs to
            values (list()): Values to process
            explode_related_record (Bool): If True return entire record dict
                instead of a reference
            record_mode (Bool): If True process value as a record value
                                else process value as a YAML value

        Returns:
            dict() or Char: record dictionary if fetch_record else reference
        """

        # -- (Record -> YAML)
        if record_mode:
            record_list = []
            for value in values:
                # Retrieve the record based on the ID provided in the value
                record = comodel.browse(value)

                # If the context specifies to explode the related record,
                # return its dictionary representation
                if explode_related_record:
                    record_list.append(
                        record._prepare_record_for_yaml() if record else False
                    )

                # Otherwise, return just the reference
                # (or False if record does not exist)
                else:
                    record_list.append(record.reference if record else False)

            return record_list

        # -- (YAML -> Record)
        # Step 1: Process value in normal mode
        record_ids = []

        for value in values:
            record = False
            # If the value is a string, it is treated as a reference
            if isinstance(value, str):
                reference = value

            # If the value is a dictionary, extract the reference from it
            elif isinstance(value, dict):
                reference = value.get("reference")
                record = self._update_or_create_related_record(
                    comodel, reference, value
                )

            # Step 2: Final fallback: attempt to retrieve the record by reference
            # Return record ID or False if reference is not defined
            if not record and reference:
                record = comodel.get_by_reference(reference)

            # Save record id
            if record:
                record_ids.append(record.id)

        return record_ids

    def _update_or_create_related_record(self, model, reference, values):
        """Update related record with provided values or create a new one

        Args:
            model (BaseModel): Related record model
            values (dict()): Values to update existing/create new record
            reference (Char): Record reference

        Returns:
            record: Existing or new record
        """

        # If reference is found, retrieve the corresponding record
        if reference:
            record = model.get_by_reference(reference)

            # If the record exists, update it with the values from the dictionary
            if record:
                record.write(record._post_process_yaml_dict_values(values))
            # If the record does not exist, create a new one
            else:
                record = model.create(model._post_process_yaml_dict_values(values))

        # If there's no reference but value is a dict, create a new record
        else:
            record = model.create(model._post_process_yaml_dict_values(values))

        # Return the record's ID if it exists, otherwise return False
        return record or False
