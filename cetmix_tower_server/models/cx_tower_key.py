from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CxTowerKey(models.Model):
    """Private key storage"""

    _name = "cx.tower.key"
    _description = "Cetmix Tower private key storage"

    KEY_PLACEHOLDER = "*** Insert new value to replace existing key ***"

    name = fields.Char(required=True)
    key_ref = fields.Char(string="Key ID", index=True)
    secret_value = fields.Text(string="SSH Private Key")
    server_ids = fields.One2many(
        string="Servers", comodel_name="cx.tower.server", inverse_name="ssh_key_id"
    )
    note = fields.Char()

    _sql_constraints = [
        (
            "tower_key_ref_uniq",
            "unique (key_ref)",
            "Key ID must be unique. Try adding another Key ID explicitly",
        )
    ]

    @api.model
    def create(self, vals):
        key_ref = vals.get("key_ref", False)
        if not key_ref:
            vals.update({"key_ref": self._generate_key_ref(vals.get("name"))})
        return super().create(vals)

    @api.constrains("secret_value")
    def secret_value_unique(self):
        self_sudo = self.sudo()
        for rec in self_sudo:
            other_key = self_sudo.search(
                [("secret_value", "=", rec.secret_value), ("id", "!=", rec.id)]
            )
            if other_key:
                raise ValidationError(_("Such key already exists: %s" % other_key.name))

    def _read(self, fields):
        """Substitute fields based on api"""
        super(CxTowerKey, self)._read(fields)
        if not self.env.is_superuser() and ("secret_value" in fields or fields == []):
            # Public user used for substitution
            for record in self:
                try:
                    record._cache["secret_value"] = self.KEY_PLACEHOLDER
                except Exception:
                    # skip SpecialValue
                    # (e.g. for missing record or access right)
                    pass

    def _generate_key_ref(self, name):
        """Generate key ID based on the key name

        Args:
            name (str): _description_

        Returns:
            str: generated ref
        """
        res = name.replace(" ", "_").upper()
        return res
