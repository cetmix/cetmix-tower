# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, models


class CxTowerKey(models.Model):
    _name = "cx.tower.key"
    _inherit = [
        "cx.tower.key",
        "cx.tower.yaml.mixin",
    ]

    SECRET_VALUE_MASK = "********"

    @api.model_create_multi
    def create(self, vals_list):
        # Check secret value before creating a record
        for vals in vals_list:
            if "secret_value" in vals:
                self._check_secret_value_for_placeholder(
                    vals["secret_value"], self.SECRET_VALUE_MASK
                )
        return super().create(vals_list)

    def write(self, vals):
        # Check secret value before updating a record
        if "secret_value" in vals:
            self._check_secret_value_for_placeholder(
                vals["secret_value"], self.SECRET_VALUE_MASK
            )
        return super().write(vals)

    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "name",
            "key_type",
            "secret_value",
            "note",
        ]
        return res

    def _prepare_record_for_yaml(self):
        res = super()._prepare_record_for_yaml()

        # Replace secret value with mask
        if res.get("secret_value"):
            res["secret_value"] = self.SECRET_VALUE_MASK
        return res
