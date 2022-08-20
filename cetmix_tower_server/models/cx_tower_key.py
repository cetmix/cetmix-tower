from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CxTowerKey(models.Model):
    """Private key storage"""

    _name = "cx.tower.key"
    _description = "Cetmix Tower private key storage"

    SECRET_VALUE_PLACEHOLDER = "*** Insert new value to replace existing key ***"

    name = fields.Char(required=True)
    key_ref = fields.Char(string="Key ID", index=True)
    secret_value = fields.Text(string="SSH Private Key")
    server_ids = fields.One2many(
        string="Servers", comodel_name="cx.tower.server", inverse_name="ssh_key_id"
    )
    partner_id = fields.Many2one(help="Leave blank to use for any partner")
    note = fields.Text()

    _sql_constraints = [
        (
            "tower_key_ref_uniq",
            "unique (key_ref,partner_id)",
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
                    record._cache["secret_value"] = self.SECRET_VALUE_PLACEHOLDER
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

    def parse_code(self, code):
        """Replaces key placeholders in code with the corresponding values.
        - key has format of "#!tower.key.KEY_ID"
            eg #!cxtower.secret.GITHUB_TOKEN
        - key is terminated with space, newline or '!#'

        Args:
            code (Text): code to proceed

        Returns:
            Text: code with key values in place
        """
        key = True
        while key:
            key, key_terminator = self._extract_key(code)
            if key:
                # Replace key including key terminator
                key_to_replace = (
                    "".join((key, key_terminator)) if key_terminator else key
                )
                code = code.replace(key_to_replace, self._parse_key(key))
        return code

    def _extract_key(self, code):
        """Extract key from code

        Args:
            code (Text): _description_

        Returns:
            str, str: key or False and key terminator or False
        """
        KEY_PLACEHOLDER = "#!cxtower."

        len_code = len(code)
        # No need to search if code is too short
        if (
            len_code <= len(KEY_PLACEHOLDER) + 3
        ):  # at least one dot separator and two symbols
            return False, False

        # Beginning of the key
        index_from = code.find(KEY_PLACEHOLDER, 0)
        if index_from < 0:
            return False, False

        # Key end
        index_to = code.find(" ", index_from)

        # Extract key value
        key_string = code[index_from : index_to if index_to > 0 else len_code]
        return self._sanitize_key_string(key_string)

    def _sanitize_key_string(self, key_string):
        """Sanitize extracted key string. Leave key only.
        If key is terminated explicitly with '!#' return key terminator as well

        Args:
            key_string (str): key to sanitize

        Returns:
            str, str: sanitized key with key terminator removed, key terminator
        """
        # Key terminator
        key_terminator = False

        # Remove newlines
        key_splitted = key_string.split("\n")
        if len(key_splitted) > 1:
            key = key_splitted[0]
        else:
            key = key_string

        # Remove key terminator '!#'
        terminator_index = key.find("!#")
        if terminator_index > 0:
            key = key[0:terminator_index]
            key_terminator = "!#"

        return key, key_terminator

    def _parse_key(self, key):
        """Parse key string and call resolver based on the key type.
        Each key string consists of 3 parts:
        - key marker: #!cxtower
        - key type: e.g. "secret", "password", "login" etc
        - key ID: e.g "qwerty123", "mystrongpassword" etc

        Inherit this function to implement your own parser or resolver
        Args:
            key (str): key string

        Returns:
            str: key value or ""
        """

        res = ""
        key_parts = key.split(".")
        if len(key_parts) != 3:  # Must be 3 parts!
            return res

        key_type = key_parts[1]
        key_value = key_parts[2]

        # Parsing type 'secret'
        if key_type == "secret":
            res = self._resolve_key_type_secret(key_value)

        return res

    def _resolve_key_type_secret(self, key_value):
        """Resolve key of type "secret".
        Use this function as a custom parser example

        Args:
            key_value (str): _description_

        Returns:
            str: value
        """
        if not key_value:
            return ""
        keys = self.search([("key_ref", "=", key_value)]).sudo()
        if keys:
            res = keys[0].secret_value
        else:
            res = ""

        return res
