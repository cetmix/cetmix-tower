import yaml

from odoo import _, api, fields, models


class CxTowerYamlImportWiz(models.TransientModel):
    _name = "cx.tower.yaml.import.wiz"
    _description = "Cetmix Tower YAML Import Wizard"
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
    secret_list = fields.Char(
        readonly=True,
        help="List of secrets present in the YAML file",
        compute="_compute_secret_list",
    )

    @api.depends("model_name")
    def _compute_model_description(self):
        """Compute model description"""
        for record in self:
            record.model_description = self.env[record.model_name]._description

    @api.depends("yaml_code")
    def _compute_secret_list(self):
        """Compute list of secrets present in the YAML file"""
        for record in self:
            secret_list = self._extract_secret_names(yaml.safe_load(record.yaml_code))
            if secret_list:
                record.secret_list = _(
                    "After import, please check and provide secret values"
                    " if needed for the following secrets: %(secrets)s",
                    secrets=", ".join(secret_list),
                )
            else:
                record.secret_list = False

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

    def _extract_secret_names(self, data: dict) -> list:
        """Extract names of secrets from YAML data.

        Args:
            data (dict): YAML data.

        Returns:
            list: List of unique secret names.
        """
        secret_names = set()

        def _recursive_extract(node):
            """Recursively extract secret names from nested structures."""
            if isinstance(node, dict):
                if "secret_ids" in node and isinstance(node["secret_ids"], list):
                    for item in node["secret_ids"]:
                        if isinstance(item, dict) and "name" in item:
                            secret_names.add(item["name"])

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
