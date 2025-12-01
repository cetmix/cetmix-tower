# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


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

    def action_import_yaml(self):
        """Process YAML data and create records in Odoo"""

        self.ensure_one()

        # Parse YAML code
        yaml_data = yaml.safe_load(self.yaml_code)
        records = yaml_data.get("records")
        if not records:
            raise ValidationError(_("YAML file doesn't contain any records"))

        # Cache models
        model_cache = {}
        odoo_record_ids = []

        # Process each record
        for record in records:
            record_reference = record.get("reference")
            if not record_reference:
                raise ValidationError(_("Record reference is missing"))
            model_name = record.get("cetmix_tower_model")
            if not model_name:
                raise ValidationError(
                    _("Record model is missing for record %s", record_reference)
                )

            # Get model from cache or create new one
            model = model_cache.get(model_name)
            if not model:
                model = self.env[
                    f"cx.tower.{model_name.replace('_', '.')}"
                ].with_context(skip_ssh_settings_check=(model_name == "server"))
                model_cache[model_name] = model

            # Get existing record by reference
            # NOTE: we don't validate models here because they are
            # already validated in the file upload wizard.
            odoo_record = model.get_by_reference(record_reference)

            # Skip
            if self.if_record_exists == "skip" and odoo_record:
                _logger.info(
                    "Skipping record '%s' in model '%s'" " because it already exists",
                    record_reference,
                    model_name,
                )
                continue

            # Update existing record
            elif self.if_record_exists == "update" and odoo_record:
                try:
                    record_values = model.with_context(
                        force_create_related_record=False,
                    )._post_process_yaml_dict_values(record)
                    odoo_record.with_context(
                        from_yaml=True,
                    ).write(record_values)
                    odoo_record_ids.append(odoo_record.id)
                except Exception as e:
                    raise ValidationError(
                        _(
                            "Error updating record %(reference)s: %(error)s",
                            reference=record_reference,
                            error=e,
                        )
                    ) from e
                _logger.info(
                    f"Updated record '{record_reference}' in model '{model_name}'"
                )
                continue

            # Or create a new record
            record_values = model.with_context(
                force_create_related_record=self.if_record_exists == "create",
            )._post_process_yaml_dict_values(record)
            try:
                odoo_record = model.with_context(
                    from_yaml=True,
                ).create(record_values)
                odoo_record_ids.append(odoo_record.id)
            except Exception as e:
                raise ValidationError(
                    _(
                        "Error creating record '%(reference)s' in model"
                        " '%(model)s': %(error)s",
                        reference=record_reference,
                        model=model_name,
                        error=e,
                    )
                ) from e
            _logger.info(f"Created record '{record_reference}' in model '{model_name}'")

        # No records were created or updated
        if not odoo_record_ids:
            action = {
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

        # All records from the same model
        elif len(model_cache) == 1:
            model = list(model_cache.values())[0]
            action = {
                "name": _("Import result: %(model)s", model=model._description),
                "type": "ir.actions.act_window",
                "res_model": model._name,
                "target": "current",
                "domain": [("id", "in", odoo_record_ids)],
            }
            if len(odoo_record_ids) == 1:
                # Open single record in form view
                action["res_id"] = odoo_record_ids[0]
                action["view_mode"] = "form"
            else:
                # Open list view of all records
                action["view_mode"] = "list,form"

        # Records from different models
        else:
            model_names = ", ".join(
                f"'{model._description}'" for model in model_cache.values()
            )
            action = {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Record Import"),
                    "message": _(
                        "Records of the following models were created "
                        "or updated: %(models)s",
                        models=model_names,
                    ),
                    "sticky": True,
                    "type": "success",
                    "next": {"type": "ir.actions.act_window_close"},
                },
            }

        return action

    def _extract_secret_names(self, data: dict) -> list:
        """Extract names of secrets from YAML data.

        Supports both formats:
        - secret_ids -> [{name: ...}]
        - secret_ids -> [{key_id: {name: ...}}]
        """
        secret_names = set()

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
