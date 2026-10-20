# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import copy
import logging

import yaml
from markupsafe import escape

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class CxTowerYamlImportWiz(models.TransientModel):
    """
    Process YAML data and create records in Odoo.
    """

    _name = "cx.tower.yaml.import.wiz"
    _description = "Cetmix Tower YAML Import Wizard"

    yaml_code = fields.Text(readonly=True)
    model_names = fields.Char(readonly=True, help="Models to create records in")
    if_record_exists = fields.Selection(
        selection=[
            ("skip", "Skip record"),
            ("update", "Update existing record"),
            ("create", "Create a new record"),
        ],
        default="skip",
        required=True,
        help="What to do if record with the same reference already exists",
    )
    secret_list = fields.Html(
        help="List of secrets present in the YAML file (formatted as HTML list)",
        compute="_compute_secret_list",
    )
    preview_code = fields.Boolean(
        help="Toggle to show or hide YAML code preview",
    )
    manifest_name = fields.Char(
        readonly=True, compute="_compute_yaml_data", string="Snippet Name"
    )
    manifest_summary = fields.Char(
        readonly=True, compute="_compute_yaml_data", string="Summary"
    )
    manifest_description = fields.Text(
        readonly=True, compute="_compute_yaml_data", string="Description"
    )
    manifest_author_string = fields.Char(
        readonly=True,
        compute="_compute_yaml_data",
        help="Comma-separated list",
        string="Author",
    )
    manifest_version = fields.Char(
        readonly=True, compute="_compute_yaml_data", string="Version"
    )
    manifest_website = fields.Char(
        readonly=True, compute="_compute_yaml_data", string="Website"
    )
    manifest_license = fields.Char(
        readonly=True, compute="_compute_yaml_data", string="License"
    )
    manifest_license_text = fields.Text(
        readonly=True, compute="_compute_yaml_data", string="License text"
    )
    manifest_price = fields.Float(
        readonly=True, compute="_compute_yaml_data", string="Price"
    )
    manifest_currency = fields.Char(
        readonly=True, compute="_compute_yaml_data", string="Currency"
    )

    @api.depends("yaml_code")
    def _compute_secret_list(self):
        """Compute list of secrets present in the YAML file"""
        for record in self:
            yaml_data = yaml.safe_load(record.yaml_code or "{}")
            secret_list = self._extract_secret_names(yaml_data)
            if not secret_list:
                record.secret_list = False
                continue

            # Build deterministic HTML list of secrets
            items = "".join(f"<li>{escape(name)}</li>" for name in sorted(secret_list))
            secrets_html = f"<ul>{items}</ul>"

            record.secret_list = _(
                "Following secrets are used in the code:<br/>%(secrets)s",
                secrets=secrets_html,
            )

    @api.depends("yaml_code")
    def _compute_yaml_data(self):
        for record in self:
            data = yaml.safe_load(record.yaml_code or "{}")

            manifest = data.get("manifest", {}) if isinstance(data, dict) else {}
            authors = manifest.get("author")
            if isinstance(authors, list | tuple):
                manifest_author_string = ", ".join(authors)
            elif isinstance(authors, str):
                manifest_author_string = authors
            else:
                manifest_author_string = False

            record.update(
                {
                    "manifest_name": manifest.get("name"),
                    "manifest_summary": manifest.get("summary"),
                    "manifest_description": manifest.get("description"),
                    "manifest_author_string": manifest_author_string,
                    "manifest_version": manifest.get("version"),
                    "manifest_website": manifest.get("website"),
                    "manifest_license": manifest.get("license"),
                    "manifest_license_text": manifest.get("license_text"),
                    "manifest_price": manifest.get("price"),
                    "manifest_currency": manifest.get("currency"),
                }
            )

    def _get_import_model(self, model_name, model_cache):
        """Return cached model configured for YAML import."""
        model = model_cache.get(model_name)
        if model is None:
            model = self.env[self._technical_model_name(model_name)].with_context(
                skip_ssh_settings_check=(model_name == "server")
            )
            model_cache[model_name] = model
        return model

    def _get_import_model_context(
        self,
        deferred_m2o_queue,
        deferred_x2m_queue,
        deferred_m2m_queue,
        reference_map,
        file_keys,
        force_create_related_record,
        owner_id=None,
    ):
        """Build context used while converting YAML values to record values.

        Args:
            deferred_m2o_queue (list): Many2one links written after the main pass.
            deferred_x2m_queue (list): Owned children created after the main pass.
            deferred_m2m_queue (list): Many2many links written after the main pass.
            reference_map (dict): File ``(model, reference)`` to record.
            file_keys (set): Every ``(model, reference)`` defined in the file.
            force_create_related_record (bool): Create nested records instead of
                updating ones that already use the reference.
            owner_id (int | None): Existing owner, used to match dependency rows.

        Returns:
            dict: Context values.
        """
        context = {
            "yaml_deferred_m2o_queue": deferred_m2o_queue,
            "yaml_deferred_x2m_queue": deferred_x2m_queue,
            "yaml_deferred_m2m_queue": deferred_m2m_queue,
            "yaml_reference_map": reference_map,
            "yaml_file_record_keys": file_keys,
            "force_create_related_record": force_create_related_record,
        }
        if owner_id:
            context["yaml_import_owner_id"] = owner_id
        return context

    def _technical_model_name(self, model_name):
        """Return the Odoo model name for a YAML model name.

        Args:
            model_name (str): Name from ``cetmix_tower_model``.

        Returns:
            str | None: Technical model name, or None when the key is missing.
        """
        if not model_name:
            return None
        return f"cx.tower.{model_name.replace('_', '.')}"

    def _collect_nested_file_keys(self, model, values, keys):
        """Add references of owned children to the file index.

        Args:
            model (BaseModel): Owner model.
            values (dict): YAML record.
            keys (set): ``(model, reference)`` pairs found in the file.
        """
        for field_name, field in model._fields.items():
            if model._yaml_export_mode(field) != "explode":
                continue
            children = values.get(field_name)
            if not isinstance(children, list) or not field.comodel_name:
                continue
            comodel = self.env[field.comodel_name]
            for child in children:
                if not isinstance(child, dict):
                    continue
                reference = child.get("reference")
                if reference:
                    keys.add((comodel._name, reference))
                self._collect_nested_file_keys(comodel, child, keys)

    def _prescan_yaml_records(self, records):
        """Index file references and the records this import treats as roots.

        A file with no root marker treats every top-level record as a root.

        Args:
            records (list): YAML records.

        Returns:
            tuple: File keys and the set of root ``(model, reference)`` pairs.
        """
        keys = set()
        parsed = []
        for record in records:
            reference = record.get("reference")
            model_name = self._technical_model_name(record.get("cetmix_tower_model"))
            if reference and model_name:
                if model_name not in self.env:
                    parsed.append((record, None, None))
                    continue
                model = self.env[model_name]
                keys.add((model_name, reference))
                self._collect_nested_file_keys(model, record, keys)
            parsed.append((record, model_name, reference))
        marked = {
            (model_name, reference)
            for record, model_name, reference in parsed
            if model_name and reference and record.get("cetmix_tower_root")
        }
        if marked:
            return keys, marked
        roots = {
            (model_name, reference)
            for _record, model_name, reference in parsed
            if model_name and reference
        }
        return keys, roots

    def _format_deferred_resolution_error(self, item):
        """Format one unresolved deferred relation entry."""
        return _(
            "Record %(record_model)s '%(record_reference)s': field "
            "'%(field)s' could not resolve "
            "%(target_model)s '%(target_reference)s'",
            record_model=item["record_model"],
            record_reference=item["record_reference"],
            field=item["field_name"],
            target_model=item["target_model"],
            target_reference=item["target_reference"],
        )

    def _record_from_import(self, model_name, reference, record_id=None):
        """Resolve a record from the import map, then by id, then by reference.

        Args:
            model_name (str): Technical model name.
            reference (str): Reference as written in the file.
            record_id (int | None): Id stamped when the record was created.

        Returns:
            recordset: Matching record, or an empty recordset.
        """
        model = self.env[model_name]
        reference_map = self.env.context.get("yaml_reference_map") or {}
        mapped = reference_map.get((model_name, reference)) if reference else None
        if mapped and mapped.exists():
            return mapped
        if record_id:
            record = model.browse(record_id).exists()
            if record:
                return record
        if reference:
            return model.get_by_reference(reference)
        return model.browse()

    def _apply_deferred_m2o_imports(self, deferred_queue):
        """Write many2one links that were waiting for a later record.

        Args:
            deferred_queue (list): Queued many2one links.

        Raises:
            ValidationError: A link still cannot be resolved.
        """
        unresolved = []
        for item in deferred_queue:
            record = self._record_from_import(
                item["record_model"],
                item["record_reference"],
                item.get("record_id"),
            )
            target = self._record_from_import(
                item["target_model"], item["target_reference"]
            )
            if not record or not target:
                unresolved.append(item)
                continue
            record.with_context(from_yaml=True).write({item["field_name"]: target.id})

        if unresolved:
            details = "\n".join(
                self._format_deferred_resolution_error(item) for item in unresolved
            )
            raise ValidationError(
                _("Deferred relation resolution failed:\n%(details)s", details=details)
            )

    def _format_deferred_x2m_resolution_error(self, item):
        """Format one unresolved deferred x2m child entry."""
        return _(
            "Record '%(record)s': field '%(field)s' could not resolve "
            "%(target_model)s '%(target_reference)s'",
            record=item["record_reference"],
            field=item["field_name"],
            target_model=item["target_model"],
            target_reference=item["target_reference"],
        )

    def _apply_deferred_x2m_imports(self, deferred_queue):
        """Create owned children that were waiting for a later record.

        Args:
            deferred_queue (list): Queued child records.

        Raises:
            ValidationError: A child still cannot be resolved.
        """
        unresolved = []
        for item in deferred_queue:
            owner_model = self.env[item["record_model"]]
            owner_record = self._record_from_import(
                item["record_model"],
                item["record_reference"],
                item.get("record_id"),
            )
            target_record = self._record_from_import(
                item["target_model"], item["target_reference"]
            )
            if not owner_record or not target_record:
                unresolved.append(item)
                continue

            owner_field = owner_model._fields[item["field_name"]]
            inverse_name = owner_field.inverse_name
            child_model = self.env[item["child_model"]]
            child_values = child_model.with_context(
                yaml_deferred_m2o_queue=[],
                yaml_deferred_x2m_queue=[],
                yaml_deferred_m2m_queue=[],
                yaml_reference_map=self.env.context.get("yaml_reference_map"),
                yaml_file_record_keys=self.env.context.get("yaml_file_record_keys"),
                force_create_related_record=False,
            )._post_process_yaml_dict_values(copy.deepcopy(item["values"]))
            child_values[inverse_name] = owner_record.id
            if not child_values.get(item["deferred_field"]):
                unresolved.append(item)
                continue

            # Guard against creating a duplicate child when the same
            # (owner, target) pair was already inserted — e.g. because a
            # duplicate YAML entry queued the same item twice, or the child
            # was created by a first-pass write after the queue was built.
            existing = child_model.search(
                [
                    (inverse_name, "=", owner_record.id),
                    (item["deferred_field"], "=", child_values[item["deferred_field"]]),
                ],
                limit=1,
            )
            if existing:
                child_model._remember_yaml_reference(
                    child_model, item["values"].get("reference"), existing
                )
                continue

            child_model.with_context(
                from_yaml=True,
                yaml_reference_map=self.env.context.get("yaml_reference_map"),
                yaml_file_record_keys=self.env.context.get("yaml_file_record_keys"),
            ).create(child_values)

        if unresolved:
            details = "\n".join(
                self._format_deferred_x2m_resolution_error(item) for item in unresolved
            )
            raise ValidationError(
                _("Deferred relation resolution failed:\n%(details)s", details=details)
            )

    def _tag_deferred_queue_items(self, queue, start, record_id, owner_model_name):
        """Stamp deferred queue items that belong to *owner_model_name*.

        Nested imports queue deferred relations for inner models (e.g. plan lines)
        while creating a top-level record (e.g. jet template). Only items whose
        ``record_model`` matches the record that was just created must receive
        ``record_id``; others keep reference-based resolution in the apply pass.

        Args:
            queue (list): The deferred import queue (m2o or x2m).
            start (int): Index of the first item belonging to the current batch.
            record_id (int): Database ID of the newly created/updated owner record.
            owner_model_name (str): Technical name of the model *record_id* belongs to.
        """
        for item in queue[start:]:
            if item["record_model"] == owner_model_name:
                item["record_id"] = record_id

    def _apply_deferred_m2m_imports(self, deferred_queue):
        """Link queued many2many records after the main import pass.

        Args:
            deferred_queue (list): Queued many2many links.

        Raises:
            ValidationError: A link still cannot be resolved.
        """
        unresolved = []
        for item in deferred_queue:
            record = self._record_from_import(
                item["record_model"],
                item["record_reference"],
                item.get("record_id"),
            )
            target = self._record_from_import(
                item["target_model"], item["target_reference"]
            )
            if not record or not target:
                unresolved.append(item)
                continue
            record.with_context(from_yaml=True).write(
                {item["field_name"]: [(4, target.id)]}
            )

        if unresolved:
            details = "\n".join(
                self._format_deferred_resolution_error(item) for item in unresolved
            )
            raise ValidationError(
                _("Deferred relation resolution failed:\n%(details)s", details=details)
            )

    def _import_result_action(self, root_records):
        """Open the root records after import.

        One root opens in form view. Several roots of one model open in list
        view. Any other result keeps the notification.

        Args:
            root_records (list): Root records, created, updated or linked.

        Returns:
            dict: Window action.
        """
        if not root_records:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Record Import"),
                    "message": _("No records were created or updated"),
                    "sticky": True,
                    "type": "warning",
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }

        if len(root_records) == 1:
            record = root_records[0]
            return {
                "name": _("Import result: %(model)s", model=record._description),
                "type": "ir.actions.act_window",
                "res_model": record._name,
                "target": "current",
                "res_id": record.id,
                "view_mode": "form",
            }

        model_names = {record._name for record in root_records}
        if len(model_names) == 1:
            record = root_records[0]
            return {
                "name": _("Import result: %(model)s", model=record._description),
                "type": "ir.actions.act_window",
                "res_model": record._name,
                "target": "current",
                "domain": [("id", "in", [item.id for item in root_records])],
                "view_mode": "list,form",
            }

        descriptions = ", ".join(
            f"'{description}'"
            for description in dict.fromkeys(
                record._description for record in root_records
            )
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Record Import"),
                "message": _(
                    "Records of the following models were created "
                    "or updated: %(models)s",
                    models=descriptions,
                ),
                "sticky": True,
                "type": "success",
                "next": {"type": "ir.actions.act_window_close"},
            },
        }

    def _link_existing_yaml_children(self, model, values, reference_map):
        """Remember nested records of an owner this import does not write.

        Skip and Create leave an existing record unchanged. Its nested
        children stay in the database, and a later reference must find them.

        Args:
            model (BaseModel): Owner model.
            values (dict): YAML record.
            reference_map (dict): File reference map.
        """
        for field in model._fields.values():
            if model._yaml_export_mode(field) != "explode":
                continue
            children = values.get(field.name)
            if not isinstance(children, list) or not field.comodel_name:
                continue
            comodel = self.env[field.comodel_name]
            for child in children:
                if not isinstance(child, dict):
                    continue
                reference = child.get("reference")
                key = (comodel._name, reference) if reference else None
                if key and key not in reference_map:
                    existing = comodel.get_by_reference(reference)
                    if existing:
                        reference_map[key] = existing
                self._link_existing_yaml_children(comodel, child, reference_map)

    def action_import_yaml(self):
        """Process YAML data and create records in Odoo.

        Create mode copies only the root records. Every other record in the
        file is linked when it already exists, and created when it does not.

        Returns:
            dict: Action that opens the root records, or a notification.

        Raises:
            ValidationError: The file has no records, a record has no
            reference or model, or a record cannot be saved.
        """

        self.ensure_one()

        # Parse YAML code
        yaml_data = yaml.safe_load(self.yaml_code)
        records = yaml_data.get("records")
        if not records:
            raise ValidationError(_("YAML file doesn't contain any records"))

        file_keys, root_keys = self._prescan_yaml_records(records)
        model_cache = {}
        reference_map = {}
        root_records = []
        deferred_m2o_queue = []
        deferred_x2m_queue = []
        deferred_m2m_queue = []

        with self.env.cr.savepoint():
            for record in records:
                m2o_start = len(deferred_m2o_queue)
                x2m_start = len(deferred_x2m_queue)
                m2m_start = len(deferred_m2m_queue)
                record_reference = record.get("reference")
                if not record_reference:
                    raise ValidationError(_("Record reference is missing"))
                model_name = record.get("cetmix_tower_model")
                if not model_name:
                    raise ValidationError(
                        _("Record model is missing for record %s", record_reference)
                    )

                model = self._get_import_model(model_name, model_cache)
                # NOTE: we don't validate models here because they are
                # already validated in the file upload wizard.
                existing = model.get_by_reference(record_reference)
                is_root = (model._name, record_reference) in root_keys
                create_new = not existing or (
                    self.if_record_exists == "create" and is_root
                )
                link_only = (
                    existing
                    and not create_new
                    and (
                        self.if_record_exists == "skip"
                        or (self.if_record_exists == "create" and not is_root)
                    )
                )

                if link_only:
                    model.with_context(
                        yaml_reference_map=reference_map
                    )._remember_yaml_reference(model, record_reference, existing)
                    self._link_existing_yaml_children(model, record, reference_map)
                    if is_root:
                        root_records.append(existing)
                    _logger.info(
                        "Skipping record '%s' in model '%s' because it already exists",
                        record_reference,
                        model_name,
                    )
                    continue

                import_context = self._get_import_model_context(
                    deferred_m2o_queue,
                    deferred_x2m_queue,
                    deferred_m2m_queue,
                    reference_map,
                    file_keys,
                    force_create_related_record=create_new,
                    owner_id=existing.id if existing and not create_new else None,
                )
                try:
                    record_values = model.with_context(
                        **import_context
                    )._post_process_yaml_dict_values(record)
                    if existing and not create_new:
                        existing.with_context(from_yaml=True, **import_context).write(
                            record_values
                        )
                        odoo_record = existing
                        _logger.info(
                            "Updated record '%s' in model '%s'",
                            record_reference,
                            model_name,
                        )
                    else:
                        odoo_record = model.with_context(
                            from_yaml=True, **import_context
                        ).create(record_values)
                        _logger.info(
                            "Created record '%s' in model '%s'",
                            record_reference,
                            model_name,
                        )
                except Exception as e:
                    if existing and not create_new:
                        raise ValidationError(
                            _(
                                "Error updating record %(reference)s: %(error)s",
                                reference=record_reference,
                                error=e,
                            )
                        ) from e
                    raise ValidationError(
                        _(
                            "Error creating record '%(reference)s' in model"
                            " '%(model)s': %(error)s",
                            reference=record_reference,
                            model=model_name,
                            error=e,
                        )
                    ) from e

                model.with_context(
                    yaml_reference_map=reference_map
                )._remember_yaml_reference(model, record_reference, odoo_record)
                for queue, start in (
                    (deferred_m2o_queue, m2o_start),
                    (deferred_x2m_queue, x2m_start),
                    (deferred_m2m_queue, m2m_start),
                ):
                    self._tag_deferred_queue_items(
                        queue, start, odoo_record.id, model._name
                    )
                if is_root:
                    root_records.append(odoo_record)

            importer = self.with_context(
                yaml_reference_map=reference_map,
                yaml_file_record_keys=file_keys,
            )
            importer._apply_deferred_m2o_imports(deferred_m2o_queue)
            importer._apply_deferred_x2m_imports(deferred_x2m_queue)
            importer._apply_deferred_m2m_imports(deferred_m2m_queue)

        return self._import_result_action(root_records)

    def _extract_secret_names(self, data: dict) -> list:
        """Extract names of secrets from YAML data.

        Supports nested records and a flat file. In a flat file each key is
        its own record, and ``secret_ids`` / ``ssh_key_id`` are references.

        - secret_ids -> [{name: ...}]
        - secret_ids -> [{key_id: {name: ...}}]
        - records -> [{cetmix_tower_model: key, name: ...}]

        Args:
            data (dict): Parsed YAML document.

        Returns:
            list: Secret and SSH key names found in the file.
        """
        secret_names = set()
        records = data.get("records") if isinstance(data, dict) else None
        if isinstance(records, list):
            for record in records:
                if (
                    isinstance(record, dict)
                    and record.get("cetmix_tower_model") == "key"
                    and record.get("name")
                ):
                    secret_names.add(record["name"])

        def _recursive_extract(node):
            """Recursively extract secret names from nested structures."""
            if isinstance(node, dict):
                if "secret_ids" in node and isinstance(node["secret_ids"], list):
                    for item in node["secret_ids"]:
                        if not isinstance(item, dict):
                            continue

                        # Format 1: direct name
                        if "name" in item:
                            secret_names.add(item["name"])
                        # Format 2: nested key_id -> name
                        elif (
                            "key_id" in item
                            and isinstance(item["key_id"], dict)
                            and "name" in item["key_id"]
                        ):
                            secret_names.add(item["key_id"]["name"])

                # Handle single ssh_key_id
                if "ssh_key_id" in node and isinstance(node["ssh_key_id"], dict):
                    if "name" in node["ssh_key_id"]:
                        secret_names.add(node["ssh_key_id"]["name"])

                # Recursively process the rest of the dictionary
                for value in node.values():
                    _recursive_extract(value)

            elif isinstance(node, list):
                for item in node:
                    _recursive_extract(item)

        _recursive_extract(data)
        return list(secret_names)
