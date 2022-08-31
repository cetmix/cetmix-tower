from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CxTowerKey(models.Model):
    """Private key storage"""

    _name = "cx.tower.key"
    _description = "Cetmix Tower private key storage"

    SECRET_VALUE_PLACEHOLDER = "*** Insert new value to replace the existing one ***"

    name = fields.Char(required=True)
    key_ref = fields.Char(string="Key ID", index=True)
    key_type = fields.Selection(
        selection=[
            ("k", "SSH Key"),
            ("s", "Secret"),
        ],
        required=True,
        default="k",
    )
    key_ref_complete = fields.Char(
        string="Key Reference",
        compute="_compute_key_ref_complete",
        help="Key reference for inline usage",
    )
    secret_value = fields.Text(string="SSH Private Key")
    server_ssh_ids = fields.One2many(
        string="Used as SSH Key",
        comodel_name="cx.tower.server",
        inverse_name="ssh_key_id",
        readonly=True,
        help="Used as SSH key in the following servers",
    )
    server_id = fields.Many2one(
        comodel_name="cx.tower.server",
        help="Used for selected server only. Leave blank to use globally",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner", help="Leave blank to use for any partner"
    )
    note = fields.Text()

    _sql_constraints = [
        (
            "tower_key_ref_uniq",
            "unique (key_ref,partner_id,server_id)",
            "Key ID must be unique. Try adding another Key ID explicitly",
        )
    ]

    def _compute_key_ref_complete(self):
        """Compute key reference
        Eg '#!cxtower.secret.KEY'
        """
        for rec in self:
            if rec.key_ref:
                key_prefix = self._compose_key_prefix(rec.key_type)
                if key_prefix:
                    rec.key_ref_complete = ".".join(
                        ("#!cxtower", key_prefix, rec.key_ref)
                    )
                else:
                    rec.key_ref_complete = None
            else:
                rec.key_ref_complete = None

    def _compose_key_prefix(self, key_type):
        """Compose key prefix based on key type.
        Override to implement own key prefixes.


        Args:
            key_type (_type_): _description_

        Raises:
            ValidationError: _description_

        Returns:
            Char: key prefix
        """
        if key_type == "s":
            key_prefix = "secret"
        else:
            key_prefix = None
        return key_prefix

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
                [
                    ("secret_value", "=", rec.secret_value),
                    ("id", "!=", rec.id),
                    ("partner_id", "=", rec.partner_id.id if rec.partner_id else False),
                    ("server_id", "=", rec.server_id.id if rec.server_id else False),
                ]
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

    def parse_code(self, code, **kwargs):
        """Replaces key placeholders in code with the corresponding values.
        - key has format of "#!tower.key.KEY_ID"
            eg #!cxtower.secret.GITHUB_TOKEN
        - key is terminated with space, newline or '!#'

        Args:
            code (Text): code to proceed
            kwargs (dict): optional arguments

        Returns:
            Text: code with key values in place
        """

        # Get keys
        keys = self._extract_keys(code, **kwargs)

        # Replace keys with values
        for key in keys:
            # Replace key including key terminator
            key_string = key[0]
            key_terminator = key[1]
            key_to_replace = (
                "".join((key_string, key_terminator)) if key_terminator else key_string
            )
            parsed_key = self._parse_key(key_string, **kwargs)
            if parsed_key:
                code = code.replace(key_to_replace, parsed_key)

        return code

    def _extract_keys(self, code, **kwargs):
        """Extract all keys from code

        Args:
            code (Text): _description_
            **kwargs (dict): optional arguments

        Returns:
            [(str, str)]: list of key & key terminator tuples
        """
        keys = []
        extract_position = 0  # initial position
        while extract_position > -1:
            extract_position, key, key_terminator = self._extract_key(
                code, extract_position, **kwargs
            )
            if key:
                keys.append((key, key_terminator))

        return keys

    def _extract_key(self, code, extract_from=0, **kwargs):
        """Extract single key from code.

        Args:
            code (Text): code to extract from
            extract_from (Int): initial position to extract
            **kwargs (dict): optional arguments

        Returns:
            int, str, str: last_position, key or False and key terminator or False
            Last position is used to control the general extraction flow.
        """
        KEY_PLACEHOLDER = "#!cxtower."

        len_code = len(code)
        # No need to search if code is too short
        if (
            len_code <= len(KEY_PLACEHOLDER) + 3
        ):  # at least one dot separator and two symbols
            return -1, False, False

        # Beginning of the key
        index_from = code.find(KEY_PLACEHOLDER, extract_from)
        if index_from < 0:
            return index_from, False, False

        # Key end
        index_to = code.find(" ", index_from)

        # Extract key value
        key_string = code[index_from : index_to if index_to > 0 else len_code]
        key, key_terminator = self._sanitize_key_string(key_string, **kwargs)
        return index_to, key, key_terminator

    def _sanitize_key_string(self, key_string, **kwargs):
        """Sanitize extracted key string. Leave key only.
        If key is terminated explicitly with '!#' return key terminator as well

        Args:
            key_string (str): key to sanitize
            **kwargs (dict): optional arguments

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

    def _parse_key(self, key, **kwargs):
        """Parse key string and call resolver based on the key type.
        Each key string consists of 3 parts:
        - key marker: #!cxtower
        - key type: e.g. "secret", "password", "login" etc
        - key ID: e.g "qwerty123", "mystrongpassword" etc

        Inherit this function to implement your own parser or resolver
        Args:
            key (str): key string
            **kwargs (dict) optional values

        Returns:
            str: key value or False if not able to parse
        """

        res = False
        key_parts = key.split(".")
        if len(key_parts) != 3:  # Must be 3 parts!
            return res

        key_type = key_parts[1]
        key_value = key_parts[2]

        # Parsing type 'secret'
        if key_type == "secret":
            res = self._resolve_key_type_secret(key_value, **kwargs)

        return res

    def _resolve_key_type_secret(self, key_value, **kwargs):
        """Resolve key of type "secret".
        Use this function as a custom parser example

        Args:
            key_value (str): _description_
            **kwargs (dict) optional values

        Returns:
            str: value or False if not able to parse
        """
        if not key_value:
            return False

        # Prefetch all the keys with matching ref
        keys = self.search([("key_ref", "=", key_value)]).sudo()
        if not keys:
            return False

        # Try to get server specific key first
        key = False
        server_id = kwargs.get("server_id", False)
        if server_id:
            key = keys.filtered(lambda k: k.server_id.id == server_id)

        # Try to get partner specific key next
        if not key:
            partner_id = kwargs.get("partner_id", False)
            key = keys.filtered(lambda k: k.partner_id.id == partner_id)

        if not key:
            # Fallback to a global key
            key = keys
        res = key[0].secret_value
        return res
