# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import yaml

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


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
        groups="cetmix_tower_yaml.group_export,cetmix_tower_yaml.group_import",
    )

    def _compute_yaml_code(self):
        """Compute YAML code based on model record data"""

        # This is used for the file name.
        # Eg cx.tower.command record will have 'command_' prefix.
        for record in self:
            # We are reading field list for each record
            # because list of fields can differ from record to record
            yaml_code = yaml.dump(
                record._prepare_record_for_yaml(),
                Dumper=CustomDumper,
                default_flow_style=False,
                sort_keys=False,
            )
            record.yaml_code = yaml_code

    def _inverse_yaml_code(self):
        """Compose record based on provided YAML"""
        for record in self:
            if record.yaml_code:
                record_yaml_dict = yaml.safe_load(record.yaml_code)
                record_vals = record._post_process_yaml_dict_values(record_yaml_dict)
                record.update(record_vals)

    @api.constrains("yaml_code")
    def _check_yaml_code_write_access(self):
        """Check if user has access to create records from YAML"""
        if (
            not self.env.user.has_group("cetmix_tower_yaml.group_import")
            and not self.env.user._is_superuser()
        ):
            raise AccessError(_("You are not allowed to create records from YAML"))

    def create(self, vals_list):
        # Handle validation error when field values are not valid
        try:
            return super().create(vals_list)
        except ValueError as e:
            raise ValidationError(str(e)) from e

    def write(self, vals):
        # Handle validation error when field values are not valid
        try:
            return super().write(vals)
        except ValueError as e:
            raise ValidationError(str(e)) from e

    def action_open_yaml_export_wizard(self):
        """Open YAML export wizard"""

        return {
            "type": "ir.actions.act_window",
            "res_model": "cx.tower.yaml.export.wiz",
            "view_mode": "form",
            "target": "new",
        }

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

        Set 'no_yaml_service_fields' context key to skip
            service fields creation (cetmix_tower_yaml_version, cetmix_tower_model)

        Returns:
            list(): list of fields to be used as YAML keys
        """
        return ["reference"]

    def _get_force_x2m_resolve_models(self):
        """List of models that will always try to be resolved
        when referenced in x2m related fields.

        This is useful for models that should always to use existing records
        instead of creating new ones when referenced in x2m related fields.
        Such as variables or tags.

        Returns:
            List: list of models that will always try to be resolved
        """
        return ["cx.tower.variable", "cx.tower.tag", "cx.tower.os"]

    def _post_process_record_values(self, values):
        """Post process record values
            before converting them to YAML

        Args:
            values (dict): values returned by 'read' method

        Returns:
            dict(): processed values
        """
        # We don't need id because we are not using it
        values.pop("id", None)

        # Add YAML format version and model
        if not self._context.get("no_yaml_service_fields"):
            model_name = self._name.replace("cx.tower.", "").replace(".", "_")
            model_values = {
                "cetmix_tower_yaml_version": self.CETMIX_TOWER_YAML_VERSION,
                "cetmix_tower_model": model_name,
            }
        else:
            model_values = {}

        # Parse access level
        access_level = values.pop("access_level", None)
        if access_level:
            model_values.update(
                {"access_level": self.TO_YAML_ACCESS_LEVEL[access_level]}
            )

        values = {**model_values, **values}

        # Check if we need to return a record dict or just a reference
        # Use context value first, revert to the record setting if not defined
        explode_related_record = self._context.get("explode_related_record")

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

        # Remove model data because it is not a field
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

    def _process_relation_field_value(self, field, value, record_mode=False):
        """Post process One2many, Many2many or Many2one value

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
        if (
            field_type not in ["one2many", "many2many", "many2one"]
            or not field_obj.comodel_name
        ):
            return False

        comodel = self.env[field_obj.comodel_name]
        explode_related_record = self._context.get("explode_related_record")

        # Step 3: process value based on the field type
        if field_type == "many2one":
            return self._process_m2o_value(
                comodel, value, explode_related_record, record_mode
            )
        if field_type in ["one2many", "many2many"]:
            return self._process_x2m_values(
                comodel, field_type, value, explode_related_record, record_mode
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
                return (
                    record.with_context(
                        no_yaml_service_fields=True
                    )._prepare_record_for_yaml()
                    if record
                    else False
                )

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
            record = self._update_or_create_related_record(
                comodel, reference, value, create_immediately=True
            )
        else:
            return False

        # Step 2: Final fallback: attempt to retrieve the record by reference if set,
        #  return its ID or False
        if not record and reference:
            record = comodel.get_by_reference(reference)
        return record.id if record else False

    def _process_x2m_values(
        self, comodel, field_type, values, explode_related_record, record_mode=False
    ):
        """Post process many2many value
        Args:
            comodel (BaseClass): Model the value belongs to
            field_type (Char): Field type
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
                        record.with_context(
                            no_yaml_service_fields=True
                        )._prepare_record_for_yaml()
                        if record
                        else False
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
                    comodel,
                    reference,
                    value,
                    create_immediately=field_type == "many2many",
                )

            # Step 2: Final fallback: attempt to retrieve the record by reference
            # Return record ID or False if reference is not defined
            if not record and reference:
                record = comodel.get_by_reference(reference)

            # Save record data
            if record:
                record_ids.append(
                    record if isinstance(record, tuple) else (4, record.id)
                )

        return record_ids

    def _update_or_create_related_record(
        self, model, reference, values, create_immediately=False
    ):
        """Update related record with provided values or create a new one

        Args:
            model (BaseModel): Related record model
            values (dict()): Values to update existing/create new record
            reference (Char): Record reference
            create_immediately (Bool): If True create a new record immediately.
                Used for Many2one fields.

        Context:
            force_create_related_record (Bool): If True, create a new record
                even if reference is provided.

        Returns:
            record: Existing record or new record tuple
        """

        # If reference is found, retrieve the corresponding record
        if reference and (
            model._name in self._get_force_x2m_resolve_models()
            or not self._context.get("force_create_related_record")
        ):
            record = model.get_by_reference(reference)

            # If the record exists, update it with the values from the dictionary
            if record:
                record.write(record._post_process_yaml_dict_values(values))

            # If the record does not exist, create a new one
            else:
                if create_immediately:
                    record = model.create(model._post_process_yaml_dict_values(values))
                else:
                    # Use "Create" service command tuple
                    record = (0, 0, model._post_process_yaml_dict_values(values))

        # If there's no reference but value is a dict, create a new record
        else:
            if create_immediately:
                record = model.create(model._post_process_yaml_dict_values(values))
            else:
                # Use "Create" service command tuple
                record = (0, 0, model._post_process_yaml_dict_values(values))

        # Return the record's ID if it exists, otherwise return False
        return record or False

    def _check_secret_value_for_placeholder(
        self, secret_value, secret_value_placeholder
    ):
        """Check secret if secret value is the same as placeholder
        that is used as a default secret mask in YAML.
        This is done to prevent saving secret mask as a value.

        Note: we are not using a constraint because we need to check
        the value before creating or updating a record in the database.

        Args:
            secret_value (Char): secret value to check
            secret_value_placeholder (Char): secret value placeholder
        Raises:
            ValidationError: If secret value fails the check
        """

        # Prevent saving secret mask as a value
        if secret_value == secret_value_placeholder:
            raise ValidationError(
                _(
                    "Value '%(val)s' is used as default secret mask and cannot be set as a secret value",  # noqa: E501
                    val=secret_value_placeholder,
                )
            )
