from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CxTowerKey(models.Model):
    """Private key storage"""

    _name = "cx.tower.key"
    _description = "Cetmix Tower private key storage"

    KEY_PLACEHOLDER = "*** Insert new value to replace existing key ***"

    name = fields.Char(required=True)
    ssh_key = fields.Text(string="SSH Private Key")
    server_ids = fields.One2many(
        string="Servers", comodel_name="cx.tower.server", inverse_name="ssh_key_id"
    )

    @api.constrains("ssh_key")
    def ssh_key_unique(self):
        self_sudo = self.sudo()
        for rec in self_sudo:
            other_key = self_sudo.search(
                [("ssh_key", "=", rec.ssh_key), ("id", "!=", rec.id)]
            )
            if other_key:
                raise ValidationError(_("Such key already exists: %s" % other_key.name))

    def _read(self, fields):
        """Substitute fields based on api"""
        super(CxTowerKey, self)._read(fields)
        if not self.env.is_superuser() and ("ssh_key" in fields or fields == []):
            # Public user used for substitution
            for record in self:
                try:
                    record._cache["ssh_key"] = self.KEY_PLACEHOLDER
                except Exception:
                    # skip SpecialValue
                    # (e.g. for missing record or access right)
                    pass
