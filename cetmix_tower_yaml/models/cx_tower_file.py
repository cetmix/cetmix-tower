# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerFile(models.Model):
    _name = "cx.tower.file"
    _inherit = ["cx.tower.file", "cx.tower.yaml.mixin"]

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "name",
            "source",
            "file_type",
            "server_dir",
            "code",
            "file",
            "variable_ids",
            "secret_ids",
            "template_id",
            "keep_when_deleted",
            "auto_sync",
            "auto_sync_interval",
            "sync_date_next",
            "sync_date_last",
            "server_response",
        ]
        return res

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
