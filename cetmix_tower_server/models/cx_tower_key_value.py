# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CxTowerKeyValue(models.Model):
    """Secret value storage"""

    _name = "cx.tower.key.value"
    _inherit = [
        "cx.tower.reference.mixin",
        "cx.tower.vault.mixin",
    ]
    _description = "Cetmix Tower Secret Value Storage"

    SECRET_FIELDS = ["secret_value"]

    name = fields.Char(related="key_id.name", readonly=False)
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
    jet_id = fields.Many2one(
        comodel_name="cx.tower.jet",
        ondelete="cascade",
        help="Jet to which the key belongs. "
        "A jet value cannot belong to a server or a partner",
    )
    is_global = fields.Boolean(
        string="Global",
        compute="_compute_is_global",
        help="This value is applicable to all servers, partners and jets",
    )
    secret_value = fields.Text()

    @api.depends("server_id", "partner_id", "jet_id")
    def _compute_is_global(self):
        for record in self:
            record.is_global = (
                not record.server_id and not record.partner_id and not record.jet_id
            )

    @api.constrains("key_id", "server_id", "partner_id", "jet_id")
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
            if rec.jet_id:
                rec._check_jet_value()
                continue
            # Jet values are checked separately: their empty server
            # and partner must not make them look like global values
            key_values = rec.key_id.value_ids.filtered(lambda x: not x.jet_id)
            # Only one global secret value can be defined for a key
            global_values = key_values.filtered(
                lambda x, rec=rec: not x.server_id and not x.partner_id
            )
            if len(global_values) > 1:
                raise ValidationError(
                    _("Only one global secret value can be defined for a key")
                )
            # Only one secret value can be defined for a server and partner
            server_partner_values = key_values.filtered(
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
            server_values = key_values.filtered(
                lambda x, rec=rec: x.server_id == rec.server_id and not x.partner_id
            )
            if len(server_values) > 1:
                raise ValidationError(
                    _("Only one secret value can be defined for a server")
                )
            # Only one secret value can be defined for a partner
            partner_values = key_values.filtered(
                lambda x, rec=rec: x.partner_id == rec.partner_id and not x.server_id
            )
            if len(partner_values) > 1:
                raise ValidationError(
                    _("Only one secret value can be defined for a partner")
                )

    def _check_jet_value(self):
        """Validate a secret value that belongs to a jet.

        A jet value cannot also belong to a server or a partner,
        and only one value can be defined for a key and a jet.

        Raises:
            ValidationError: the value also belongs to a server or a partner,
                or the key already has a value for this jet.
        """
        self.ensure_one()
        if self.server_id or self.partner_id:
            raise ValidationError(
                self.env._(
                    "A secret value that belongs to a jet"
                    " cannot belong to a server or a partner"
                )
            )
        jet_values = self.key_id.value_ids.filtered(lambda x: x.jet_id == self.jet_id)
        if len(jet_values) > 1:
            raise ValidationError(
                self.env._("Only one secret value can be defined for a jet")
            )

    @api.returns("self", lambda value: value.id)
    def copy(self, default=None):
        """Copy key value. Ensure secret value is copied.

        Args:
            default (dict, optional): Default values. Defaults to None.

        Returns:
            self: Copied key value
        """
        default = default or {}
        default["secret_value"] = self._get_secret_value("secret_value")
        return super().copy(default=default)
