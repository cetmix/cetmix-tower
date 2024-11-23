from odoo import api, fields, models


class CxTowerKeyMixin(models.AbstractModel):
    _name = "cx.tower.key.mixin"
    _description = "Mixin for managing secrets"

    secret_ids = fields.Many2many(
        comodel_name="cx.tower.key",
        compute="_compute_secret_ids",
        compute_sudo=True,
        readonly=True,
        store=True,
        string="Secrets",
    )

    @api.depends("code")
    def _compute_secret_ids(self):
        """
        Compute the secret IDs based on the references found in the code field.

        This method updates the secret_ids Many2many field by extracting secret
        references from the code field. If no code is present, the field is cleared.
        It ensures updates are only triggered when there are differences between
        the current and new secret IDs.
        """
        for record in self:
            if record.code:
                new_secrets = self._extract_secret_ids(record.code)

                # This will create a recordset that contains the difference
                if record.secret_ids != new_secrets:
                    record.secret_ids = new_secrets
            else:
                record.secret_ids = [(5, 0, 0)]

    @api.model
    def _extract_secret_ids(self, code):
        """
        Extract secret IDs based on references found in the given `code`.

        Args:
            code: Text containing potential secret references.

        Returns:
            list: List of secret IDs corresponding to the references in `code`.
        """
        key_model = self.env["cx.tower.key"]
        key_strings = key_model._extract_key_strings(code)

        key_refs = []
        for key_string in key_strings:
            key_parts = key_model._extract_key_parts(key_string)
            if key_parts:
                key_refs.append(key_parts[1])

        return key_model.search(
            [
                ("reference", "in", key_refs),
            ]
        )
