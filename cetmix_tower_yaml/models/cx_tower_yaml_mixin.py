# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import copy
import logging

import yaml

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)
DEFERRED_M2O_IMPORT = object()

# Carried on create vals so the import can map the reference written in the
# file to the record Odoo actually stored (the reference mixin may suffix it).
# Popped before the ORM sees the vals.
YAML_FILE_REFERENCE_KEY = "_yaml_file_reference"

YAML_EXPORT_EXPLODE = "explode"
YAML_EXPORT_INCLUDE = "include"
YAML_EXPORT_REFERENCE = "reference"
JET_TEMPLATE_DEPENDENCY_MODEL = "cx.tower.jet.template.dependency"
SCHEDULED_TASK_CV_MODEL = "cx.tower.scheduled.task.cv"


class CustomDumper(yaml.Dumper):
    """Custom dumper to ensures code
    is properly dumped in YAML
    """

    def represent_scalar(self, tag, value, style=None):
        if isinstance(value, str) and "\n" in value:
            style = "|"
        return super().represent_scalar(tag, value, style)


class YamlExportCollector:
    """
    Collector for YAML export.
    Tracks unique records by their (model_name, reference) tuple to avoid duplicates.
    """

    def __init__(self):
        """
        Initialize the collector.
        """
        self.added_references = set()

    def add(self, key):
        """
        Add a record to the collector if its reference is unique.
        :param key: tuple, key of the record
        """
        if key and key not in self.added_references:
            self.added_references.add(key)

    def is_added(self, key):
        """
        Check by (model, reference) tuple.
        :param key: tuple, key of the record
        :return: bool
        """
        return key in self.added_references


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

    def _valid_field_parameter(self, field, name):
        """Accept ``yaml_export`` on models that inherit this mixin.

        Odoo logs a warning for field parameters the model does not declare.
        The attribute is set on the YAML model, not on a shared mixin field,
        so models that do not inherit this mixin never see it.

        Args:
            field (odoo.fields.Field): Field being set up.
            name (str): Parameter name.

        Returns:
            bool: Whether the parameter is allowed.
        """
        return name == "yaml_export" or super()._valid_field_parameter(field, name)

    def _yaml_export_mode(self, field):
        """Return the export mode declared on this field.

        A related field copies ``yaml_export`` from its target
        (``odoo/fields.py`` ``setup_related``). That copy is not an export
        decision: only a mode present in the field's own ``_extra_keys``
        counts. ``odoo/fields.py`` records those keys in ``_setup_attrs``.

        Args:
            field (odoo.fields.Field): Field to inspect.

        Returns:
            bool | str | None: ``True``, ``explode``, ``include``,
            ``reference``, or None.
        """
        if "yaml_export" not in field._extra_keys:
            return None
        return field.yaml_export

    def _compute_yaml_code(self):
        """Compute YAML code based on model record data.

        One record, under the same rules as a file export: ``include`` fields
        are references and no other records are added.
        """
        # This is used for the file name.
        # Eg cx.tower.command record will have 'command_' prefix.
        for record in self:
            # We are reading field list for each record
            # because list of fields can differ from record to record
            record.yaml_code = self._convert_dict_to_yaml(
                record._prepare_record_for_yaml()
            )

    def _inverse_yaml_code(self):
        """Compose record based on provided YAML"""
        for record in self:
            if record.yaml_code:
                record_yaml_dict = yaml.safe_load(record.yaml_code)
                record_vals = record._post_process_yaml_dict_values(record_yaml_dict)
                record.update(record_vals)

    @api.constrains("yaml_code")
    def _check_yaml_code_write_access(self):
        """
        Check if user has access to create records from YAML.
        This is checked only when user already has access to export YAML.
        Otherwise, the field is not accessible due to security group.
        """
        if self.env.user.has_group("cetmix_tower_yaml.group_export") and (
            not self.env.user.has_group("cetmix_tower_yaml.group_import")
            and not self.env.user._is_superuser()
        ):
            raise AccessError(_("You are not allowed to create records from YAML"))

    @api.model_create_multi
    def create(self, vals_list):
        """Create records and remember file references from this import.

        The reference mixin may store a suffixed reference. The import map
        must still find the new record by the reference written in the file,
        including owned children created through ``(0, 0, vals)``.

        Args:
            vals_list (list): Value dicts.

        Returns:
            recordset: Created records.

        Raises:
            ValidationError: Field values are not valid for the model.
        """
        file_references = [
            vals.pop(YAML_FILE_REFERENCE_KEY, None) for vals in vals_list
        ]
        # Handle validation error when field values are not valid
        try:
            records = super().create(vals_list)
        except ValueError as e:
            raise ValidationError(str(e)) from e
        reference_map = self.env.context.get("yaml_reference_map")
        if reference_map is not None:
            for file_reference, record in zip(file_references, records, strict=False):
                if file_reference:
                    reference_map[(self._name, file_reference)] = record
        return records

    def write(self, vals):
        """Write values, dropping the import-only file reference key.

        Args:
            vals (dict): Values to write.

        Returns:
            bool: Result of the super call.

        Raises:
            ValidationError: Field values are not valid for the model.
        """
        if isinstance(vals, dict):
            vals.pop(YAML_FILE_REFERENCE_KEY, None)
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

    def _convert_dict_to_yaml(self, values):
        """Converts Python dictionary to YAML string.

        This is a helper function that is designed to be used
        by any models that need to convert a dictionary to YAML.

           Args:
               values (Dict): Dictionary containing data
                    to be converted to YAML format
           Returns:
               Text: YAML string
           Raises:
               ValidationError: If values is not a dictionary
                   or YAML conversion fails
        """
        if not isinstance(values, dict):
            raise ValidationError(_("Values must be a dictionary"))
        try:
            yaml_code = yaml.dump(
                values,
                Dumper=CustomDumper,
                default_flow_style=False,
                sort_keys=False,
            )
            return yaml_code
        except (yaml.YAMLError, UnicodeEncodeError) as e:
            raise ValidationError(
                _(
                    "Failed to convert dictionary" " to YAML: %(error)s",
                    error=str(e),
                )
            ) from e

    def _get_yaml_field_names(self):
        """Return exported field names in file order.

        ``reference`` is always exported by this mixin. ``name`` follows when
        it carries ``yaml_export``. Every other exported field keeps its
        position in ``_fields``.

        Returns:
            list: Field names.
        """
        names = ["reference"]
        name_field = self._fields.get("name")
        if name_field is not None and self._yaml_export_mode(name_field):
            names.append("name")
        for field_name, field in self._fields.items():
            if field_name in ("reference", "name"):
                continue
            if self._yaml_export_mode(field):
                names.append(field_name)
        return names

    def _prepare_record_for_yaml(self):
        """Reads and processes current record before converting it to YAML

        Returns:
            dict: values ready for YAML conversion
        """
        self.ensure_one()
        yaml_keys = self._get_yaml_field_names()
        record_dict = self.read(fields=yaml_keys)[0]
        return self._post_process_record_values(record_dict)

    def _get_force_x2m_resolve_models(self):
        """List of models that will always try to be resolved
        when referenced in x2m related fields.

        This is useful for models that should always use existing records
        instead of creating new ones when referenced in x2m related fields.
        Such as variables or tags.

        Returns:
            List: list of models that will always try to be resolved
        """
        return [
            "cx.tower.variable",
            "cx.tower.variable.option",
            "cx.tower.tag",
            "cx.tower.os",
            "cx.tower.key",
        ]

    def _iter_yaml_export_dependencies(self, include_related):
        """Yield records that must be written before this one.

        ``explode`` children stay nested. Their ``include`` targets are
        still visited, in field order then recordset order. ``reference``
        fields are not walked. With related records disabled, nothing is
        yielded: ``include`` values stay reference strings.

        Args:
            include_related (bool): Whether to follow ``include`` fields.

        Yields:
            recordset: One related record.
        """
        self.ensure_one()
        for field_name, field in self._fields.items():
            mode = self._yaml_export_mode(field)
            if mode == YAML_EXPORT_EXPLODE:
                for child in self[field_name]:
                    yield from child._iter_yaml_export_dependencies(include_related)
            elif mode == YAML_EXPORT_INCLUDE and include_related:
                for target in self[field_name]:
                    if target:
                        yield target

    def _collect_yaml_export_records(self, include_related, collector, stack, ordered):
        """Append this record after the records it uses.

        A link back into the current chain is left for later in the file.
        The same record is emitted once.

        Args:
            include_related (bool): Whether to follow ``include`` fields.
            collector (YamlExportCollector): Records already emitted.
            stack (set): ``(model, reference)`` keys of the current chain.
            ordered (list): Records in export order.
        """
        for record in self:
            reference = record.reference
            key = (record._name, reference or record.id)
            if key in stack or collector.is_added(key):
                continue
            stack.add(key)
            for dependency in record._iter_yaml_export_dependencies(include_related):
                dependency._collect_yaml_export_records(
                    include_related, collector, stack, ordered
                )
            stack.remove(key)
            collector.add(key)
            ordered.append(record)

    def _has_meaningful_yaml_value(self, value):
        """Return whether a YAML value contains meaningful payload."""
        if value is False or value is None or value == "":
            return False
        if isinstance(value, dict):
            if set(value.keys()) <= {"reference"}:
                return bool(value.get("reference"))
            return any(
                self._has_meaningful_yaml_value(item)
                for key, item in value.items()
                if key != "reference"
            )
        if isinstance(value, list):
            return any(self._has_meaningful_yaml_value(item) for item in value)
        return True

    def _get_reference_only_yaml_relation_reference(self, value):
        """Return reference for reference-only YAML relation values.

        Args:
            value (str | dict): YAML relation value.

        Returns:
            str | bool: Reference if the value is reference-only, otherwise False.
        """
        if isinstance(value, str):
            return value
        if isinstance(value, dict) and set(value.keys()) <= {"reference"}:
            return value.get("reference") or False
        return False

    def _first_yaml_reference(self, value):
        """Return the reference carried by a YAML relation value.

        Args:
            value (str | dict | bool): YAML relation value.

        Returns:
            str | bool: Reference, or False when the value has none.
        """
        if isinstance(value, str):
            return value or False
        if isinstance(value, dict):
            return value.get("reference") or False
        return False

    def _yaml_reference_pending(self, comodel, reference):
        """Tell whether a file reference still has to be imported.

        Args:
            comodel (BaseModel): Target model.
            reference (str): Reference as written in the file.

        Returns:
            bool: True when the pair is in this file and not yet linked.
        """
        if not reference:
            return False
        file_keys = self.env.context.get("yaml_file_record_keys")
        if not file_keys:
            return False
        key = (comodel._name, reference)
        if key not in file_keys:
            return False
        reference_map = self.env.context.get("yaml_reference_map") or {}
        return key not in reference_map

    def _resolve_yaml_reference(self, comodel, reference):
        """Resolve a reference from this import, then from the database.

        Args:
            comodel (BaseModel): Target model.
            reference (str): Reference as written in the file.

        Returns:
            recordset: Matching record, or an empty recordset.
        """
        if not reference:
            return comodel.browse()
        reference_map = self.env.context.get("yaml_reference_map")
        if reference_map is not None:
            mapped = reference_map.get((comodel._name, reference))
            if mapped and mapped.exists():
                return mapped
        return comodel.get_by_reference(reference)

    def _remember_yaml_reference(self, comodel, reference, record):
        """Store a file reference that was linked instead of created.

        Args:
            comodel (BaseModel): Record model.
            reference (str): Reference as written in the file.
            record (BaseModel): Record the reference points at.
        """
        reference_map = self.env.context.get("yaml_reference_map")
        if reference_map is not None and reference and record:
            reference_map[(comodel._name, reference)] = record

    def _queue_deferred_m2o_import(self, field, comodel, value):
        """Queue a many2one whose target appears later in the file.

        Args:
            field (str): Owner field name.
            comodel (BaseModel): Related model.
            value (str | dict): YAML relation value.

        Returns:
            bool: True when the relation was queued.

        A required many2one stays in the first write. Only a link the
        record can be saved without is postponed.
        """
        queue = self.env.context.get("yaml_deferred_m2o_queue")
        if queue is None or self._fields[field].required:
            return False
        target_reference = self._get_reference_only_yaml_relation_reference(value)
        if not target_reference or not self._yaml_reference_pending(
            comodel, target_reference
        ):
            return False
        record_reference = self.env.context.get("yaml_import_record_reference")
        if not record_reference:
            return False
        queue.append(
            {
                "record_model": self._name,
                "record_reference": record_reference,
                "field_name": field,
                "target_model": comodel._name,
                "target_reference": target_reference,
            }
        )
        return True

    def _queue_deferred_m2m_import(self, field, comodel, reference):
        """Queue a many2many link whose target appears later in the file.

        Args:
            field (str): Owner field name.
            comodel (BaseModel): Related model.
            reference (str): Target reference.

        Returns:
            bool: True when the link was queued.
        """
        queue = self.env.context.get("yaml_deferred_m2m_queue")
        if queue is None or not reference:
            return False
        if not self._yaml_reference_pending(comodel, reference):
            return False
        record_reference = self.env.context.get("yaml_import_record_reference")
        if not record_reference:
            return False
        queue.append(
            {
                "record_model": self._name,
                "record_reference": record_reference,
                "field_name": field,
                "target_model": comodel._name,
                "target_reference": reference,
            }
        )
        return True

    def _pending_yaml_relation(self, comodel, value):
        """Return one not-yet-imported relation inside a child payload.

        Args:
            comodel (BaseModel): Child model.
            value (dict): YAML child record.

        Returns:
            tuple | None: ``(field_name, target_model, target_reference)``
            or None when this child can be saved now.

        A many2one written as a reference to a later record postpones the
        child. Nested records are saved with the child. The link back to
        the record being imported is not a later record.
        """
        owner_reference = self.env.context.get("yaml_import_record_reference")
        for key, item in value.items():
            field = comodel._fields.get(key)
            if not field or field.type != "many2one" or not field.comodel_name:
                continue
            reference = self._get_reference_only_yaml_relation_reference(item)
            if not reference:
                continue
            target_model = self.env[field.comodel_name]
            if target_model._name == self._name and reference == owner_reference:
                continue
            if self._yaml_reference_pending(target_model, reference):
                return key, target_model._name, reference
        return None

    def _queue_deferred_x2m_import(self, field, comodel, value, pending):
        """Queue an owned child that links to a record later in the file.

        Args:
            field (str): Owner x2m field name.
            comodel (BaseModel): Child model.
            value (dict): YAML child record.
            pending (tuple): Field, target model and target reference.

        Returns:
            bool: True when the child was queued.
        """
        queue = self.env.context.get("yaml_deferred_x2m_queue")
        if queue is None:
            return False
        record_reference = self.env.context.get("yaml_import_record_reference")
        if not record_reference:
            return False
        field_name, target_model, target_reference = pending
        queue.append(
            {
                "record_model": self._name,
                "record_reference": record_reference,
                "field_name": field,
                "child_model": comodel._name,
                "deferred_field": field_name,
                "target_model": target_model,
                "target_reference": target_reference,
                "values": copy.deepcopy(value),
            }
        )
        return True

    def _skip_empty_scheduled_task_cv(self, comodel, value):
        """Skip a scheduled-task custom value that carries no payload.

        Args:
            comodel (BaseModel): Child model.
            value (dict): YAML child record.

        Returns:
            bool: True when the row must not be created.
        """
        return (
            comodel._name == SCHEDULED_TASK_CV_MODEL
            and not self._has_meaningful_yaml_value(value)
        )

    def _existing_template_dependency_command(self, comodel, value):
        """Match a dependency row by template pair when the owner exists.

        Dependency rows cannot be edited. A matching pair is left as it is.
        Any other pair is created. ``False`` means this value is not a
        dependency of an existing template and the caller uses the generic path.

        Args:
            comodel (BaseModel): Related model.
            value (dict): YAML child record.

        Returns:
            tuple | None | bool: Create command, None to skip, or False.
        """
        if comodel._name != JET_TEMPLATE_DEPENDENCY_MODEL:
            return False
        owner_id = self.env.context.get("yaml_import_owner_id")
        if not owner_id:
            return False
        required_reference = self._first_yaml_reference(
            value.get("template_required_id")
        )
        target = self._resolve_yaml_reference(
            self.env["cx.tower.jet.template"], required_reference
        )
        if target:
            existing = comodel.search(
                [
                    ("template_id", "=", owner_id),
                    ("template_required_id", "=", target.id),
                ],
                limit=1,
            )
            if existing:
                self._remember_yaml_reference(comodel, value.get("reference"), existing)
                return None
        child_values = comodel._post_process_yaml_dict_values(dict(value))
        return (0, 0, child_values)

    def _post_process_record_values(self, values):
        """Post process record values before converting them to YAML.

        Key order is ``cetmix_tower_model``, ``cetmix_tower_root`` for roots,
        then the fields from ``_get_yaml_field_names``. ``access_level`` stays
        in that field order.

        Args:
            values (dict): values returned by 'read' method

        Context:
            remove_empty_values: if set will remove empty values from the record
            yaml_export_root: if set, mark the record as an export root
            no_yaml_service_fields: skip cetmix_tower_model and the root marker

        Returns:
            dict(): processed values
        """
        # We don't need id because we are not using it
        values.pop("id", None)

        # Parse access level in place so it keeps its field-order position
        access_level = values.get("access_level")
        if access_level:
            values["access_level"] = self.TO_YAML_ACCESS_LEVEL[access_level]

        # Check if we need to remove empty values
        # Currently only x2m fields are supported
        remove_empty_values = self.env.context.get("remove_empty_values")
        new_values = {}
        for key, value in values.items():
            field = self._fields.get(key)
            if not field or field.type not in ("many2one", "one2many", "many2many"):
                new_values[key] = value
                continue
            if not value and remove_empty_values:
                continue
            new_values[key] = self._process_relation_field_value(
                key, value, record_mode=True
            )

        if self.env.context.get("no_yaml_service_fields"):
            return new_values

        ordered = {
            "cetmix_tower_model": self._name.replace("cx.tower.", "").replace(".", "_"),
        }
        if self.env.context.get("yaml_export_root"):
            ordered["cetmix_tower_root"] = True
        ordered.update(new_values)
        return ordered

    def _stamp_yaml_file_reference(self, values):
        """Attach the file reference so create() can register the record.

        Args:
            values (dict): Values about to be created or written.
        """
        reference = values.get("reference")
        if self.env.context.get("yaml_reference_map") is not None and reference:
            values[YAML_FILE_REFERENCE_KEY] = reference

    def _post_process_yaml_dict_values(self, values):
        """Post process dictionary values generated from YAML code

        Args:
            values (dict): Dictionary generated from YAML

        Returns:
            dict(): Post-processed values
        """
        # Remove model data because it is not a field
        values.pop("cetmix_tower_model", None)
        values.pop("cetmix_tower_root", None)

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
        supported_keys = self._get_yaml_field_names()
        filtered_values = {k: v for k, v in values.items() if k in supported_keys}

        # Post process m2o fields
        for key, value in list(filtered_values.items()):
            field = self._fields.get(key)
            if not field or field.type not in ("many2one", "one2many", "many2many"):
                continue
            processed_value = self.with_context(
                yaml_import_record_reference=filtered_values.get("reference"),
            )._process_relation_field_value(key, value, record_mode=False)
            if processed_value is DEFERRED_M2O_IMPORT:
                filtered_values.pop(key, None)
            else:
                filtered_values.update({key: processed_value})

        self._stamp_yaml_file_reference(filtered_values)
        return filtered_values

    def _process_relation_field_value(self, field, value, record_mode=False):
        """Post process One2many, Many2many or Many2one value

        Args:
            field (Char): Field the value belongs to
            value (Char): Value to process
            record_mode (Bool): If True process value as a record value
                                else process value as a YAML value
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

        # Step 3: process value based on the field type
        if field_type == "many2one":
            return self._process_m2o_value(field, comodel, value, record_mode)
        if field_type in ["one2many", "many2many"]:
            return self._process_x2m_values(
                field, comodel, field_type, value, record_mode
            )

        # Step 4: fall back if field type is not supported
        return False

    def _yaml_relation_export_value(self, field, record):
        """Serialize one related record using its ``yaml_export`` mode.

        Args:
            field (str): Field name.
            record (BaseModel): Related record.

        Returns:
            dict | str | bool: Nested record, reference, or False.
        """
        if not record:
            return False
        mode = self._yaml_export_mode(self._fields[field])
        if mode == YAML_EXPORT_EXPLODE:
            return record.with_context(
                no_yaml_service_fields=True,
                yaml_export_root=False,
            )._prepare_record_for_yaml()
        return record.reference or False

    def _process_m2o_value(self, field, comodel, value, record_mode=False):
        """Post process many2one value

        Args:
            field (Char): Field the value belongs to
            comodel (BaseClass): Model the value belongs to
            value (Char): Value to process
            record_mode (Bool): If True process value as a record value
                                else process value as a YAML value

        Returns:
            dict() or Char: record dictionary if fetch_record else reference

        Raises:
            ValidationError: A required link points at a record that is
            still later in the file.
        """
        # -- (Record -> YAML)
        if record_mode:
            record = comodel.browse(value[0])
            return self._yaml_relation_export_value(field, record)

        # -- (YAML -> Record)
        reference = False
        if isinstance(value, str):
            reference = value
        elif isinstance(value, dict):
            reference = value.get("reference")
        else:
            return False

        reference_only = self._get_reference_only_yaml_relation_reference(value)
        # A required column cannot be left empty and filled later: the insert
        # is rejected before the deferred pass. Fail here, before that insert,
        # and do not attach the record already stored under this reference.
        if (
            reference_only
            and self._fields[field].required
            and self._yaml_reference_pending(comodel, reference_only)
        ):
            record_reference = self.env.context.get("yaml_import_record_reference")
            raise ValidationError(
                _(
                    "Deferred relation resolution failed:\n"
                    "Record %(record_model)s '%(record_reference)s': field "
                    "'%(field)s' could not resolve "
                    "%(target_model)s '%(target_reference)s'",
                    record_model=self._name,
                    record_reference=record_reference,
                    field=field,
                    target_model=comodel._name,
                    target_reference=reference_only,
                )
            )
        if reference_only and self._queue_deferred_m2o_import(field, comodel, value):
            return DEFERRED_M2O_IMPORT

        record = False
        if isinstance(value, dict) and not reference_only:
            record = self._update_or_create_related_record(
                comodel, reference, value, create_immediately=True
            )
        elif reference:
            record = self._resolve_yaml_reference(comodel, reference)
        return record.id if record else False

    def _process_x2m_values(
        self,
        field,
        comodel,
        field_type,
        values,
        record_mode=False,
    ):
        """Post process many2many value

        Args:
            field (Char): Field the value belongs to
            comodel (BaseClass): Model the value belongs to
            field_type (Char): Field type
            values (list()): Values to process
            record_mode (Bool): If True process value as a record value
                                else process value as a YAML value

        Returns:
            dict() or Char: record dictionary if fetch_record else reference
        """
        # -- (Record -> YAML)
        if record_mode:
            return [
                self._yaml_relation_export_value(field, comodel.browse(value))
                for value in values
            ]

        # -- (YAML -> Record)
        record_ids = []
        for value in values:
            command = self._import_x2m_item(field, comodel, field_type, value)
            if command:
                record_ids.append(command)
        return record_ids

    def _import_x2m_item(self, field, comodel, field_type, value):
        """Turn one YAML x2m item into an ORM command.

        Args:
            field (str): Owner field name.
            comodel (BaseModel): Related model.
            field_type (str): ``one2many`` or ``many2many``.
            value (str | dict): YAML item.

        Returns:
            tuple | None: ORM command, or None when the item is skipped.
        """
        if isinstance(value, str):
            if self._queue_deferred_m2m_import(field, comodel, value):
                return None
            record = self._resolve_yaml_reference(comodel, value)
            return (4, record.id) if record else None

        if not isinstance(value, dict):
            return None

        if self._skip_empty_scheduled_task_cv(comodel, value):
            return None

        if field_type == "one2many":
            pending = self._pending_yaml_relation(comodel, value)
            if pending and self._queue_deferred_x2m_import(
                field, comodel, value, pending
            ):
                return None
            dependency_command = self._existing_template_dependency_command(
                comodel, value
            )
            if dependency_command is None:
                return None
            if dependency_command:
                return dependency_command

        reference_only = self._get_reference_only_yaml_relation_reference(value)
        if reference_only and field_type == "many2many":
            if self._queue_deferred_m2m_import(field, comodel, reference_only):
                return None
            record = self._resolve_yaml_reference(comodel, reference_only)
            return (4, record.id) if record else None

        reference = value.get("reference")
        record = self._update_or_create_related_record(
            comodel,
            reference,
            value,
            create_immediately=field_type == "many2many",
        )
        if not record:
            return None
        if isinstance(record, tuple):
            return record
        return (4, record.id)

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
        reference_map = self.env.context.get("yaml_reference_map")
        mapped = None
        if reference_map is not None and reference:
            mapped = reference_map.get((model._name, reference))
            if mapped and not mapped.exists():
                mapped = None

        # If reference is found, retrieve the corresponding record
        if mapped or (
            reference
            and (
                model._name in self._get_force_x2m_resolve_models()
                or not self.env.context.get("force_create_related_record")
            )
        ):
            record = mapped or model.get_by_reference(reference)
            # If the record exists, update it with the values from the dictionary
            if record:
                # Remove reference from values to avoid possible consequences
                values.pop("reference", None)
                record.with_context(from_yaml=True).write(
                    record._post_process_yaml_dict_values(values)
                )
                self._remember_yaml_reference(model, reference, record)

            # If the record does not exist, create a new one
            else:
                record = self._create_related_from_yaml_values(
                    model, reference, values, create_immediately
                )

        # If there's no reference but value is a dict, create a new record
        else:
            record = self._create_related_from_yaml_values(
                model, reference, values, create_immediately
            )

        # Return the record's ID if it exists, otherwise return False
        return record or False

    def _create_related_from_yaml_values(
        self, model, reference, values, create_immediately
    ):
        """Create a related record, or skip a reference-only stub.

        Args:
            model (BaseModel): Related model.
            reference (str): Record reference.
            values (dict): YAML values.
            create_immediately (bool): Create now instead of returning a command.

        Returns:
            recordset | tuple | bool: Created record, ``(0, 0, vals)``, or False.
        """
        if set(values.keys()) <= {"reference"}:
            _logger.warning(
                "Attempted to import a record for model '%s' "
                "with reference "
                "'%s', but only the 'reference' field was provided. "
                "Creation will be skipped until the target record "
                "exists.",
                model._name,
                reference,
            )
            return False
        child_values = model._post_process_yaml_dict_values(values)
        if create_immediately:
            return model.with_context(from_yaml=True).create(child_values)
        return (0, 0, child_values)
