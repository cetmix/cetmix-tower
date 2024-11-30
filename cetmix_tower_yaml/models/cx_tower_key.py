# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, api, models
from odoo.exceptions import ValidationError


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
                self._check_secret_value(vals["secret_value"])
        return super().create(vals)

    def write(self, vals):
        # Check secret value before updating a record
        if "secret_value" in vals:
            self._check_secret_value(vals["secret_value"])
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

    def _check_secret_value(self, secret_value):
        """Check secret value before creating or updating a record
        We are not using a constraint because we need to check
        the value before creating or updating a record in the database.

        Args:
            secret_value (Char): secret value to check

        Raises:
            ValidationError: If secret value fails the check
        """

        # Prevent saving secret mask as a value
        if secret_value == self.SECRET_VALUE_MASK:
            raise ValidationError(
                _(
                    "Value '%(val)s' is used as default secret mask and cannot be set as a secret value",  # noqa: E501
                    val=self.SECRET_VALUE_MASK,
                )
            )
