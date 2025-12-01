import binascii
from base64 import b64decode

import yaml

from odoo import _, fields, models
from odoo.exceptions import ValidationError


class CxTowerYamlImportWizUpload(models.TransientModel):
    """
    Upload YAML file and perform initial validation.
    Submit YAML data to import wizard for further processing.
    """

    _name = "cx.tower.yaml.import.wiz.upload"
    _description = "Cetmix Tower YAML Import Wizard Upload"

    file_name = fields.Char()
    yaml_file = fields.Binary(required=True)

    def action_import_yaml(self):
        """Parse YAML data to the import wizard

        Returns:
            Action Window: Action to open the import wizard
        """

        decoded_file = self._extract_yaml_data()

        import_wizard = self.env["cx.tower.yaml.import.wiz"].create(
            {
                "yaml_code": decoded_file,
            }
        )

        return {
            "type": "ir.actions.act_window",
            "res_model": "cx.tower.yaml.import.wiz",
            "res_id": import_wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def _extract_yaml_data(self):
        """Extract data from YAML file and validate them

        Returns:
            decoded_file (Text): YAML code
            Raises:
                ValidationError: If the YAML file is invalid
                or contains unsupported data
        """

        self.ensure_one()

        # Decode base64 file
        try:
            raw_bytes = b64decode(self.yaml_file or b"")
        except (TypeError, binascii.Error) as e:
            # Not a valid base-64 payload
            raise ValidationError(_("File is not a valid base64-encoded file")) from e

        if not raw_bytes:
            raise ValidationError(_("File is empty"))

        try:
            decoded_file = raw_bytes.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValidationError(_("YAML file cannot be decoded properly")) from e

        # Parse YAML file
        try:
            yaml_data = yaml.safe_load(decoded_file)
        except yaml.YAMLError as e:
            raise ValidationError(_("Invalid YAML file")) from e

        if not yaml_data or not isinstance(yaml_data, dict):
            raise ValidationError(_("Yaml file doesn't contain valid data"))

        # Check Cetmix Tower YAML version
        yaml_version = yaml_data.pop("cetmix_tower_yaml_version", None)
        supported_version = self.env["cx.tower.yaml.mixin"].CETMIX_TOWER_YAML_VERSION
        if (
            yaml_version
            and isinstance(yaml_version, int)
            and yaml_version > supported_version
        ):
            raise ValidationError(
                _(
                    "YAML version is higher than version"
                    " supported by your Cetmix Tower instance."
                    " %(code_version)s > %(tower_version)s",
                    code_version=yaml_version,
                    tower_version=supported_version,
                )
            )

        # Get records from YAML
        records = yaml_data.get("records")
        if not records:
            raise ValidationError(_("YAML file doesn't contain any records"))

        # Collect and validate all record models
        ir_model_obj = self.env["ir.model"].sudo()
        unique_models = {}

        # First pass: check all records have models and collect unique models
        for record in records:
            record_model = record.get("cetmix_tower_model")
            if not record_model:
                raise ValidationError(
                    _(
                        "Record model is missing for record %s",
                        record.get("reference", ""),
                    )
                )
            if record_model not in unique_models:
                odoo_model = f"cx.tower.{record_model}".replace("_", ".")
                unique_models[record_model] = odoo_model

        # Second pass: validate all unique models in a single query
        odoo_models = list(unique_models.values())
        valid_models = {
            model.model: model
            for model in ir_model_obj.search([("model", "in", odoo_models)])
        }

        # Third pass: check models exist and support YAML import
        for record_model, odoo_model in unique_models.items():
            if odoo_model not in valid_models:
                raise ValidationError(_("'%s' is not a valid model", record_model))
            if not hasattr(self.env[odoo_model], "yaml_code"):
                raise ValidationError(
                    _("Model '%s' does not support YAML import", record_model)
                )
        return decoded_file
