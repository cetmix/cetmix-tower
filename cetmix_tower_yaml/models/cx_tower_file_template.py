# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerFileTemplate(models.Model):
    _name = "cx.tower.file.template"
    _inherit = ["cx.tower.file.template", "cx.tower.yaml.mixin"]

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "name",
            "source",
            "file_type",
            "server_dir",
            "file_name",
            "keep_when_deleted",
            "tag_ids",
            "note",
            "code",
            "variable_ids",
            "secret_ids",
        ]
        return res
