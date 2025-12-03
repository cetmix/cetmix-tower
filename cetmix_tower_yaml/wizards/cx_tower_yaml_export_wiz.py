# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import base64
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..models.cx_tower_yaml_mixin import YamlExportCollector

FILE_HEADER = """
# This file is generated with Cetmix Tower.
# Details and documentation: https://cetmix.com/tower
"""

CLEAN_STR = re.compile(r"[^a-z0-9_]")


class CxTowerYamlExportWiz(models.TransientModel):
    """Cetmix Tower YAML Export Wizard"""

    _name = "cx.tower.yaml.export.wiz"
    _description = "Cetmix Tower YAML Export Wizard"

    yaml_code = fields.Text()
    yaml_file_name = fields.Char(
        string="YAML File Name",
        size=255,
        default=lambda self: self._default_yaml_file_name(),
        help="Snippet file name without extension, eg 'my_snippet'",
    )

    explode_child_records = fields.Boolean(
        default=True,
        help="Add entire child record definitions to the exported YAML file. "
        "Otherwise only references to child records will be added.",
    )
    remove_empty_values = fields.Boolean(
        string="Remove Empty x2m Field Values",
        default=True,
        help="Remove empty Many2one, Many2many and One2many"
        " field values from the exported YAML file.",
    )
    preview_code = fields.Boolean()
    add_manifest = fields.Boolean()

    MANIFEST_FIELDS = [
        "manifest_template_id",
        "manifest_name",
        "manifest_author_ids",
        "manifest_version",
        "manifest_summary",
        "manifest_description",
        "manifest_website",
        "manifest_license",
        "manifest_license_text",
        "manifest_currency",
        "manifest_price",
    ]

    @api.model
    def _get_manifest_license_selection(self):
        return self.env["cx.tower.yaml.manifest.tmpl"]._selection_license()

    @api.model
    def _get_manifest_currency_selection(self):
        return self.env["cx.tower.yaml.manifest.tmpl"]._selection_currency()

    manifest_template_id = fields.Many2one(
        "cx.tower.yaml.manifest.tmpl",
    )
    manifest_name = fields.Char(
        compute="_compute_manifest",
        readonly=False,
        store=True,
        string="Snippet Name",
        help="Leave this field blank if you don't want to create a manifest",
    )
    manifest_website = fields.Char(
        compute="_compute_manifest",
        readonly=False,
        string="Website",
        store=True,
    )
    manifest_license = fields.Selection(
        selection="_get_manifest_license_selection",
        compute="_compute_manifest",
        readonly=False,
        string="License",
        store=True,
    )
    manifest_author_ids = fields.Many2many(
        "cx.tower.yaml.manifest.author",
        compute="_compute_manifest",
        readonly=False,
        string="Authors",
        store=True,
    )
    manifest_license_text = fields.Text(
        compute="_compute_manifest", readonly=False, string="License Text", store=True
    )
    manifest_currency = fields.Selection(
        selection="_get_manifest_currency_selection",
        compute="_compute_manifest",
        string="Currency",
        readonly=False,
        store=True,
    )
    manifest_summary = fields.Char(
        string="Summary",
        size=160,
        help="Short summary that includes core information. 160 symbols max",
    )
    manifest_description = fields.Text("Description")
    manifest_price = fields.Float("Price")

    manifest_version = fields.Char(
        compute="_compute_manifest",
        readonly=False,
        store=True,
        string="Version",
        help="Use the Major.Minor.Patch format, e.g. 1.2.3",
    )

    def _clean_yaml_basename(self, name: str) -> str:
        """
        Return *always-valid* basename (no extension) built from arbitrary *name*.
        """
        raw = (name or "").strip().lower()
        base = raw[:-5] if raw.endswith(".yaml") else raw
        base = CLEAN_STR.sub("_", base)
        base = re.sub(r"_+", "_", base).strip("_") or "snippet"
        return base

    def _default_yaml_file_name(self):
        """
        Build the *initial* file name shown to the user.
        Pattern: <model>_<reference>, without “.yaml” suffix.
        """
        records = self._get_model_record()
        prefix = records._name.replace("cx.tower.", "").replace(".", "_")
        ref = records.reference if len(records) == 1 else "selected"
        return f"{prefix}_{ref}"

    @api.depends("manifest_template_id")
    def _compute_manifest(self):
        mapping = {
            "manifest_author_ids": "author_ids",
            "manifest_website": "website",
            "manifest_license": "license",
            "manifest_license_text": "license_text",
            "manifest_currency": "currency",
            "manifest_version": "version",
        }
        for rec in self:
            tmpl = rec.manifest_template_id
            if not tmpl:
                continue
            for wiz_field, tmpl_field in mapping.items():
                if not rec[wiz_field]:
                    rec[wiz_field] = tmpl[tmpl_field]

            # prepend template's file prefix to YAML file name
            prefix = (tmpl.file_prefix or "").strip()
            if prefix:
                # sanitize prefix without defaulting to a placeholder like "snippet"
                raw = prefix.lower()
                sanitized_prefix = re.sub(r"_+", "_", CLEAN_STR.sub("_", raw)).strip(
                    "_"
                )
                if sanitized_prefix:
                    # use current or default base name, then clean it
                    current = rec.yaml_file_name or rec._default_yaml_file_name()
                    base = rec._clean_yaml_basename(current)
                    # avoid double-prefixing
                    if not base.startswith(f"{sanitized_prefix}_"):
                        rec.yaml_file_name = rec._clean_yaml_basename(
                            f"{sanitized_prefix}_{base}"
                        )

    @api.onchange("manifest_license")
    def _onchange_manifest_license(self):
        """Drop price and currency when user switches off the 'custom' license.

        If manifest_license != 'custom', reset manifest_price to 0.0 and
        manifest_currency to False so they won’t appear in the generated YAML.
        """
        for rec in self:
            if rec.manifest_license != "custom":
                rec.manifest_price = 0.0
                rec.manifest_currency = False

    @api.onchange("explode_child_records", "remove_empty_values", *MANIFEST_FIELDS)
    def onchange_explode_child_records(self):
        """Compute YAML code and file content."""

        self.ensure_one()

        # Get model records
        records = self._get_model_record()
        if not records:
            raise ValidationError(_("No valid records selected"))

        explode_related_record = self.explode_child_records
        remove_empty_values = self.remove_empty_values

        # Prepare YAML header
        yaml_header = FILE_HEADER.rstrip("\n")
        # Use the YAML export collector for unique records
        collector = YamlExportCollector()
        record_list = []
        for rec in records:
            record_yaml_dict = rec.with_context(
                explode_related_record=explode_related_record,
                remove_empty_values=remove_empty_values,
                yaml_collector=collector,
            )._prepare_record_for_yaml()

            if not record_yaml_dict:
                continue
            if isinstance(record_yaml_dict, dict) and list(record_yaml_dict) == [
                "reference"
            ]:
                continue

            if "cetmix_tower_model" not in record_yaml_dict:
                record_yaml_dict["cetmix_tower_model"] = rec._name.replace(
                    "cx.tower.", ""
                ).replace(".", "_")

            record_list.append(record_yaml_dict)

        if not record_list:
            self.yaml_code = f"{yaml_header}\n"
            return

        if not self.manifest_name:
            manifest = {}
        else:
            lic = (self.manifest_license or "").lower()

            fields_order = [
                ("name", self.manifest_name),
                ("summary", self.manifest_summary),
                ("description", self.manifest_description),
                ("author", self.manifest_author_ids.mapped("name")),
                ("version", self.manifest_version),
                ("website", self.manifest_website),
                ("license", self.manifest_license),
                (
                    "license_text",
                    (self.manifest_license_text or "").strip()
                    if lic == "custom"
                    else None,
                ),
                ("price", self.manifest_price),
                (
                    "currency",
                    self.manifest_currency if lic == "custom" else None,
                ),
            ]
            manifest = {k: v for k, v in fields_order if v not in (False, None, "", [])}

        result_dict = {
            "cetmix_tower_yaml_version": self.env[
                "cx.tower.yaml.mixin"
            ].CETMIX_TOWER_YAML_VERSION,
        }
        if manifest:
            result_dict["manifest"] = manifest
        result_dict["records"] = record_list

        self.yaml_code = f"{yaml_header}\n{records._convert_dict_to_yaml(result_dict)}"

    @api.onchange("yaml_file_name")
    def _onchange_yaml_file_name(self):
        """
        Live-clean the YAML file name as the user types:
        - lowercase, trim whitespace
        - replace invalid characters with “_”
        - collapse repeated underscores
        - ensure a single “.yaml” suffix
        """
        for rec in self:
            rec.yaml_file_name = rec._clean_yaml_basename(rec.yaml_file_name)

    @api.constrains("manifest_version")
    def _check_manifest_version_format(self):
        """
        Ensure the user types a semantic version (x.y.z) in the wizard itself.
        """
        semver = re.compile(r"^\d+\.\d+\.\d+$")
        for rec in self:
            if rec.manifest_version and not semver.match(rec.manifest_version):
                raise ValidationError(
                    _("Version must be in format Major.Minor.Patch, e.g. 1.2.3")
                )

    def _validate_manifest(self):
        """Logical cross-checks before saving YAML."""
        if self.manifest_price and not self.manifest_currency:
            raise ValidationError(_("Currency is required when price is specified"))
        if (self.manifest_license or "").lower() == "custom" and not (
            self.manifest_license_text or ""
        ).strip():
            raise ValidationError(_("License text is required for a custom license"))

    def write(self, vals):
        """
        Override write to always sanitize `yaml_file_name`
        before persisting, making programmatic assignments safe.
        """
        if "yaml_file_name" in vals:
            vals["yaml_file_name"] = self._clean_yaml_basename(vals["yaml_file_name"])
        return super().write(vals)

    def action_generate_yaml_file(self):
        """Save YAML file"""

        self.ensure_one()

        self._validate_manifest()
        if not self.yaml_code:
            raise ValidationError(_("No YAML code is present."))

        # Generate YAML file
        try:
            yaml_file = base64.encodebytes(self.yaml_code.encode("utf-8"))
            yaml_file_name = (
                f"{self.yaml_file_name or self._default_yaml_file_name()}.yaml"
            )
        except Exception as exc:
            raise ValidationError(
                _(
                    "Failed to encode YAML content. Please ensure all characters are UTF-8 compatible."  # noqa: E501
                )
            ) from exc

        download_wizard = self.env["cx.tower.yaml.export.wiz.download"].create(
            {
                "yaml_file": yaml_file,
                "yaml_file_name": yaml_file_name,
            }
        )

        return {
            "type": "ir.actions.act_window",
            "res_model": "cx.tower.yaml.export.wiz.download",
            "res_id": download_wizard.id,
            "target": "new",
            "view_mode": "form",
        }

    def _get_model_record(self):
        """Get model records based on context values

        Raises:
            ValidationError: in case no model or records selected

        Returns:
            ModelRecords: a recordset of selected records
        """
        model_name = self.env.context.get("active_model")
        record_ids = self.env.context.get("active_ids")
        if not model_name or not record_ids:
            raise ValidationError(_("No model or records selected"))
        return self.env[model_name].browse(record_ids)
