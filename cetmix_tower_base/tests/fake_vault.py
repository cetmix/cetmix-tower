from odoo import fields, models


class VaultResource(models.Model):
    _name = "tower.test.vault.resource"
    _inherit = "cx.tower.vault.mixin"
    _description = "Vault Test Resource"

    SECRET_FIELDS = ["secret", "required_secret", "restricted_secret"]

    name = fields.Char()
    secret = fields.Char(default="field default")
    required_secret = fields.Text(required=True, default="required default")
    restricted_secret = fields.Char(groups="base.group_system")
