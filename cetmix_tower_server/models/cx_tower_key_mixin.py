from odoo import api, fields, models


class CxTowerKeyMixin(models.AbstractModel):
    """Mixin for managing secrets and SSH keys"""

    _name = "cx.tower.key.mixin"
    _description = "Cetmix Tower Key/Secret Mixin"

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
                record.secret_ids = False

    @api.model
    def _extract_secret_ids(self, code):
        """
        Extract secret IDs based on references found in the given `code`.

        Args:
            code: Text containing potential secret references.

        Returns:
            recordset: cx.tower.key recordset of secrets found in the code.
        """
        key_model = self.env["cx.tower.key"]
        key_strings = key_model._extract_key_strings(code)

        key_refs = []
        for key_string in key_strings:
            key_parts = key_model._extract_key_parts(key_string)
            if key_parts:
                key_refs.append(key_parts[1])

        return key_model.search(self._compose_secret_search_domain(key_refs))

    def _compose_secret_search_domain(self, key_refs):
        """Compose domain for searching secrets by references.

        Args:
            key_refs (List[str]): List of secret references.

        Returns:
            List: final domain for searching secrets.
        """
        return [("reference", "in", key_refs)]
