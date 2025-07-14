from odoo import fields, models


class CxTowerVault(models.Model):
    _name = "cx.tower.vault"
    _description = "Cetmix Tower Vault"

    res_model = fields.Char(
        string="Resource Model",
        required=True,
        help="Model name of the resource that uses this vault",
    )
    res_id = fields.Many2oneReference(
        string="Resource ID",
        model_field="res_model",
        help="ID of the resource that uses this vault",
        required=True,
    )
    field_name = fields.Char(
        required=True,
        help="Name of the field that contains the secret value",
    )
    data = fields.Text(
        string="Secret Data",
        required=True,
        copy=False,
        help="The secret data to be stored in the vault",
    )

    _sql_constraints = [
        (
            "vault_unique_key",
            "UNIQUE(res_model, res_id, field_name)",
            "Each secret (model, record, field) must be unique in the vault.",
        ),
    ]
