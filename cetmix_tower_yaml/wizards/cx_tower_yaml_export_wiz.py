import base64

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CxTowerYamlExportWiz(models.TransientModel):
    _name = "cx.tower.yaml.export.wiz"
    _description = "Cetmix Tower YAML Export Wizard"

    comment = fields.Text(
        help="Comment to be added to the beginning of exported YAML file"
    )
    yaml_code = fields.Text()
    explode_child_records = fields.Boolean(
        default=True,
        help="Add entire child record definitions to the exported YAML file. "
        "Otherwise only references to child records will be added.",
    )

    @api.onchange("explode_child_records", "comment")
    def onchange_explode_child_records(self):
        """Compute YAML code and file content"""

        self.ensure_one()

        # Get model records
        records = self._get_model_record()
        explode_related_record = self.explode_child_records

        # Collact YAML code into a list
        yaml_codes = [self._text_to_yaml_comment(self.comment)] if self.comment else []

        # Concatenate all YAML codes from selected records
        for record in records:
            record_yaml_code = record.with_context(
                explode_related_record=explode_related_record
            ).yaml_code
            if record_yaml_code:
                yaml_codes.append(record_yaml_code)

        self.yaml_code = "\n".join(yaml_codes) if yaml_codes else ""

    def action_generate_yaml_file(self):
        """Save YAML file"""

        self.ensure_one()
        if not self.yaml_code:
            raise ValidationError(_("No YAML code is present."))

        # Get model records
        records = self._get_model_record()

        # Get model prefix
        model_prefix = records._name.replace("cx.tower.", "").replace(".", "_")

        # Generate YAML file
        try:
            yaml_file = base64.encodebytes(self.yaml_code.encode("utf-8"))
            yaml_file_name = (
                f"{model_prefix}_{records.reference if len(records) == 1 else 'selected'}.yaml"  # noqa: E501
            )
        except UnicodeEncodeError as exc:
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
            "view_type": "form",
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

    def _text_to_yaml_comment(self, text):
        """Convert multi line text into YAML comment

        Args:
            text (Char): Text to convert

        Returns:
            Text: Converted text
        """
        lines = text.splitlines()
        yaml_comment = "\n".join([f"# {line}" for line in lines])
        return yaml_comment
