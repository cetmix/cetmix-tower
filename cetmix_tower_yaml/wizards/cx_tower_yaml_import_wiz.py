import yaml

from odoo import api, fields, models


class CxTowerYamlImportWiz(models.TransientModel):
    _name = "cx.tower.yaml.import.wiz"
    """
    Process YAML data and create records in Odoo.
    """

    yaml_code = fields.Text(readonly=True)
    model_name = fields.Char(readonly=True, help="Model to create records in")
    model_description = fields.Char(
        string="Model", readonly=True, compute="_compute_model_description"
    )
    record_id = fields.Integer(readonly=True, help="Record ID to update")
    update_existing_record = fields.Boolean(
        default=True,
        help="If enabled, existing records will be updated with the new data."
        " Otherwise, new records will be created.",
    )

    @api.depends("model_name")
    def _compute_model_description(self):
        """Compute model description"""
        for record in self:
            record.model_description = self.env[record.model_name]._description

    def action_import_yaml(self):
        """Process YAML data and create records in Odoo"""

        self.ensure_one()

        # Parse YAML code
        yaml_data = yaml.safe_load(self.yaml_code)

        # Update existing record
        if (
            self.record_id
            and yaml_data.get("reference")
            and self.update_existing_record
        ):
            record = self.env[self.model_name].browse(self.record_id)
            record.update({"yaml_code": self.yaml_code})
        else:
            model = self.env[self.model_name]
            record_values = model.with_context(
                force_create_related_record=True
            )._post_process_yaml_dict_values(yaml_data)
            record = model.create(record_values)

        # Open created record
        return {
            "name": record.display_name,
            "type": "ir.actions.act_window",
            "res_model": self.model_name,
            "res_id": record.id,
            "view_mode": "form",
            "view_type": "form",
            "target": "current",
        }

    def action_open_existing_record(self):
        """Open existing record"""

        if self.model_name and self.record_id:
            record = self.env[self.model_name].browse(self.record_id)

            return {
                "name": record.display_name,
                "type": "ir.actions.act_window",
                "res_model": self.model_name,
                "res_id": record.id,
                "view_mode": "form",
                "view_type": "form",
                "target": "current",
            }
