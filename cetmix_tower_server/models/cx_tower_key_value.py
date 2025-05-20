# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from itertools import repeat

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CxTowerKeyValue(models.Model):
    """Secret value storage"""

    _name = "cx.tower.key.value"
    _description = "Cetmix Tower Secret Value Storage"

    key_id = fields.Many2one(
        comodel_name="cx.tower.key",
        string="Key",
        required=True,
        ondelete="cascade",
        domain="[('key_type', '=', 's')]",
    )
    server_id = fields.Many2one(
        comodel_name="cx.tower.server",
        ondelete="cascade",
        help="Server to which the key belongs",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        ondelete="cascade",
        help="Partner to which the key belongs",
    )
    is_global = fields.Boolean(
        string="Global",
        compute="_compute_is_global",
        help="This value is applicable to all servers and partners",
    )
    secret_value = fields.Text()

    @api.depends("server_id", "partner_id")
    def _compute_is_global(self):
        for record in self:
            record.is_global = not record.server_id and not record.partner_id

    @api.constrains("key_id", "server_id", "partner_id")
    def _check_key_id(self):
        for rec in self:
            if not rec.key_id:
                continue
            # Only keys of type 'secret' can have custom secret values
            if rec.key_id.key_type != "s":
                raise ValidationError(
                    _(
                        "Custom secret values can be defined"
                        " only for key type 'secret'"
                    )
                )
            # Only one global secret value can be defined for a key
            global_values = rec.key_id.value_ids.filtered(
                lambda x, rec=rec: not x.server_id and not x.partner_id
            )
            if len(global_values) > 1:
                raise ValidationError(
                    _("Only one global secret value can be defined for a key")
                )
            # Only one secret value can be defined for a server and partner
            server_partner_values = rec.key_id.value_ids.filtered(
                lambda x, rec=rec: x.server_id == rec.server_id
                and x.partner_id == rec.partner_id
            )
            if len(server_partner_values) > 1:
                raise ValidationError(
                    _(
                        "Only one secret value can be defined"
                        " for a server and partner"
                    )
                )
            # Only one secret value can be defined for a server
            server_values = rec.key_id.value_ids.filtered(
                lambda x, rec=rec: x.server_id == rec.server_id and not x.partner_id
            )
            if len(server_values) > 1:
                raise ValidationError(
                    _("Only one secret value can be defined for a server")
                )
            # Only one secret value can be defined for a partner
            partner_values = rec.key_id.value_ids.filtered(
                lambda x, rec=rec: x.partner_id == rec.partner_id and not x.server_id
            )
            if len(partner_values) > 1:
                raise ValidationError(
                    _("Only one secret value can be defined for a partner")
                )

    def _fetch_query(self, query, fields):
        """Substitute fields based on api"""
        records = super()._fetch_query(query, fields)
        if self._fields["secret_value"] in fields:
            placeholder = self.env["cx.tower.key"].SECRET_VALUE_PLACEHOLDER
            # Public user used for substitution
            self.env.cache.update(
                records,
                self._fields["secret_value"],
                repeat(placeholder),
            )
        return records

    @api.model_create_multi
    def create(self, vals_list):
        """Create a new key value and set secret value"""

        # Create records one by one to ensure that we preserve
        # the original value list order.
        # This is done to avoid possible errors when this list is modified
        # by some other module that overrides this function.
        # We also need to avoid secret values being written to the database
        # any other way besides the _set_secret_value method.
        records = self.browse()
        for vals in vals_list:
            secret_value = vals.pop("secret_value", None)
            rec = super().create(vals)
            if secret_value:
                rec._set_secret_value(secret_value)
            records |= rec
        return records

    def write(self, vals):
        """Write key values"""
        # Remove secret value from vals and set it later
        if "secret_value" in vals and not self.env.context.get("write_secret_value"):
            secret_value = vals.pop("secret_value", None)
            has_secret_value = True
        else:
            has_secret_value = False
        res = super().write(vals)
        # Set secret value
        if has_secret_value:
            for key_value in self:
                key_value._set_secret_value(secret_value)
        return res

    def _get_secret_value(self):
        """Get secret value.
        Override this method in case you need to implement custom key storages.

        Returns:
            str: secret value or None if no secret value is found
        """

        # Return None in case of empty recordset
        self.ensure_one()
        self.env.cr.execute(
            """
            SELECT secret_value
            FROM cx_tower_key_value
            WHERE id = %s
            """,
            [self.id],
        )
        result = self.env.cr.fetchone()
        if result:
            return result[0]

    def _set_secret_value(self, value=None):
        """Set secret value.
        Override this method in case you need
        to implement custom key storages.

        Args:
            value (str): secret value
        """
        self.ensure_one()
        self.with_context(write_secret_value=True).write({"secret_value": value})
        self.invalidate_recordset(["secret_value"])
