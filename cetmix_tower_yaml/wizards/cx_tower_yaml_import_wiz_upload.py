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

        Args:
            decoded_file (Text): YAML code
            model_name (Char): Name of the Odoo model, if parsed from YAML
            record_id (_type_): ID of the record, if passed from YAML

        Returns:
            Action Window: Action to open the import wizard
        """

        decoded_file, model_name, record_id = self._extract_yaml_data()

        import_wizard = self.env["cx.tower.yaml.import.wiz"].create(
            {
                "yaml_code": decoded_file,
                "model_name": model_name,
                "record_id": record_id,
                "update_existing_record": bool(record_id),
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
        """Extract data form YAML file and validate them

        Returns:
            decoded_file, model_name, record_id
            - decoded_file (Text): YAML code
            - model_name (Char): Name of the Odoo model, if resolved
            - record_id (_type_): ID of the record, if resolved

        """

        self.ensure_one()

        # Decode base64 file
        try:
            decoded_file = b64decode(self.yaml_file).decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValidationError(_("YAML file cannot be decoded properly")) from e
        except TypeError as e:
            raise ValidationError(
                _("File contains non-unicode characters or is empty")
            ) from e

        # Parse YAML file
        try:
            yaml_data = yaml.safe_load(decoded_file)
        except yaml.YAMLError as e:
            raise ValidationError(_("Invalid YAML file")) from e

        if not yaml_data or not isinstance(yaml_data, dict):
            raise ValidationError(_("Yaml file doesn't contain valid data"))

        # Get Odoo model name from YAML
        yaml_model = yaml_data.get("cetmix_tower_model")
        if not yaml_model:
            raise ValidationError(
                _("No model for import is specified in the YAML file")
            )

        model_name = f"cx.tower.{yaml_model.replace('_', '.')}"

        # Check if model exists
        try:
            model = self.env[model_name]
        except KeyError as e:
            raise ValidationError(_("Invalid model specified in the YAML file")) from e

        # Check if model supports YAML import
        if not hasattr(model, "yaml_code"):
            raise ValidationError(_("Model does not support YAML import"))

        # Check if YAML version is supported
        yaml_version = yaml_data.get("cetmix_tower_yaml_version")
        if (
            yaml_version
            and isinstance(yaml_version, int)
            and yaml_version > model.CETMIX_TOWER_YAML_VERSION
        ):
            raise ValidationError(
                _(
                    "YAML file version is not supported."
                    " You may need to update the Cetmix Tower Yaml module."
                )
            )

        # Get record id from YAML
        record_reference = yaml_data.get("reference")
        if record_reference:
            record = model.get_by_reference(record_reference)
            record_id = record and record.id or False
        else:
            record_id = False

        return decoded_file, model_name, record_id
