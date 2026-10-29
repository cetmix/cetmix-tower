# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerFile(models.Model):
    _name = "cx.tower.file"
    _inherit = ["cx.tower.file", "cx.tower.yaml.mixin"]

    name = fields.Char(yaml_export=True)
    source = fields.Selection(yaml_export=True)
    file_type = fields.Selection(yaml_export=True)
    server_dir = fields.Char(yaml_export=True)
    code = fields.Text(yaml_export=True)
    file = fields.Binary(yaml_export=True)
    variable_ids = fields.Many2many(yaml_export="include")
    secret_ids = fields.Many2many(yaml_export="include")
    template_id = fields.Many2one(yaml_export="include")
    keep_when_deleted = fields.Boolean(yaml_export=True)
    auto_sync = fields.Boolean(yaml_export=True)
    auto_sync_interval = fields.Selection(yaml_export=True)
    sync_date_next = fields.Datetime(yaml_export=True)
    sync_date_last = fields.Datetime(yaml_export=True)
    server_response = fields.Text(yaml_export=True)

    def _post_create_write(self, op_type="write"):
        # Do not pull/push files if they are being created from YAML
        if self.env.context.get("from_yaml"):
            return
        super()._post_create_write(op_type)

    def _prepare_record_for_yaml(self):
        """
        Override to drop file `code` when the source is 'server'.
        """
        record_dict = super()._prepare_record_for_yaml()

        if record_dict.get("source") == "server":
            record_dict["code"] = False

        return record_dict
