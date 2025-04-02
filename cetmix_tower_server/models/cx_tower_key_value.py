# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

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
    secret_value = fields.Text(string="Secret Value")

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

    def _read(self, fields):
        """Substitute fields based on api"""
        super()._read(fields)
        if not self.env.context.get("show_secret_value") and (
            "secret_value" in fields or fields == []
        ):
            placeholder = self.env["cx.tower.key"].SECRET_VALUE_PLACEHOLDER
            # Public user used for substitution
            for record in self:
                try:
                    record._cache["secret_value"] = placeholder
                except Exception:
                    # skip SpecialValue
                    # (e.g. for missing record or access right)
                    pass
