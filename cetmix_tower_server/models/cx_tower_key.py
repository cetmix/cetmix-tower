# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models
from odoo.osv.expression import OR


class CxTowerKey(models.Model):
    """Private key storage"""

    _name = "cx.tower.key"
    _description = "Cetmix Tower private key storage"

    KEY_PREFIX = "#!cxtower"
    KEY_TERMINATOR = "!#"
    SECRET_VALUE_PLACEHOLDER = "*** Insert new value to replace the existing one ***"
    SECRET_VALUE_SPOILER = "*****"

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
        Eg '#!cxtower.secret.KEY!#'
        """
        for rec in self:
            if rec.key_ref:
                key_prefix = self._compose_key_prefix(rec.key_type)
                if key_prefix:
                    rec.key_ref_complete = f"#!cxtower.{key_prefix}.{rec.key_ref}!#"
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            key_ref = vals.get("key_ref", False)
            if not key_ref:
                vals.update({"key_ref": self._generate_key_ref(vals.get("name"))})
        return super().create(vals_list)

    def _read(self, fields):
        """Substitute fields based on api"""
        super()._read(fields)
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

    def _parse_code_and_return_key_values(self, code, **kwargs):
        """Replaces key placeholders in code with the corresponding values,
        returning key values.

        This function is meant to be used in the flow where key values
        are needed for some follow up operations such as command log clean up.

        NB:
        - key format must follow "#!cxtower.key.KEY_ID!#" pattern.
            eg #!cxtower.secret.GITHUB_TOKEN!# for GITHUB_TOKEN key
        Args:
            code (Text): code to process
            kwargs (dict): optional arguments

        Returns:
            Dict(): 'code': Command text, 'key_values': List of key values
        """

        # No need to search if code is too short
        if len(code) <= len(self.KEY_PREFIX) + 3 + len(
            self.KEY_TERMINATOR
        ):  # at least one dot separator and two symbols
            return {"code": code, "key_values": None}

        # Get key strings
        key_strings = self._extract_key_strings(code)

        # Set key values
        key_values = []
        # Replace keys with values
        for key_string in key_strings:
            # Replace key including key terminator
            key_value = self._parse_key_string(key_string, **kwargs)
            if key_value:
                code = code.replace(key_string, key_value)

                # Save key value if not saved yet
                if key_value not in key_values:
                    key_values.append(key_value)

        return {"code": code, "key_values": key_values}

    def _parse_code(self, code, **kwargs):
        """Replaces key placeholders in code with the corresponding values.

        Args:
            code (Text): code to proceed
            kwargs (dict): optional arguments

        Returns:
            Text: code with key values in place and list of key values.
            Use key values
        """

        return self._parse_code_and_return_key_values(code, **kwargs)["code"]

    def _extract_key_strings(self, code):
        """Extract all keys from code

        Args:
            code (Text): _description_
            **kwargs (dict): optional arguments

        Returns:
            [str]: list of key stings
        """
        key_strings = []
        key_terminator_len = len(self.KEY_TERMINATOR)
        index_from = 0  # initial position
        while index_from > -1:
            index_from = code.find(self.KEY_PREFIX, index_from)

            if index_from > 0:
                # Key end
                index_to = code.find(self.KEY_TERMINATOR, index_from)

                # Extract key value only if key terminator is found
                if index_to > 0:
                    # Extract key string including key terminator
                    extract_to = index_to + key_terminator_len
                    key_string = code[index_from:extract_to]

                    # Add only if not added before
                    if key_string not in key_strings:
                        key_strings.append(key_string)
                    # Update index from
                    index_from = extract_to
                else:
                    break

        return key_strings

    def _parse_key_string(self, key_string, **kwargs):
        """Parse key string and call resolver based on the key type.
        Each key string consists of 3 parts:
        - key marker: #!cxtower
        - key type: e.g. "secret", "password", "login" etc
        - key ID: e.g "qwerty123", "mystrongpassword" etc

        Inherit this function to implement your own parser or resolver
        Args:
            key_string (str): key string
            **kwargs (dict) optional values

        Returns:
            str: key value or None if not able to parse
        """

        key_parts = (
            key_string.replace(" ", "").replace(self.KEY_TERMINATOR, "").split(".")
        )

        # Must be 3 parts including pre!
        if len(key_parts) != 3 or key_parts[0] != self.KEY_PREFIX:
            return

        key_type = key_parts[1]
        key_ref = key_parts[2]

        key_value = self._resolve_key(key_type, key_ref, **kwargs)

        return key_value

    def _resolve_key(self, key_type, key_ref, **kwargs):
        """Resolve key
        Inherit this function to implement your own resolvers

        Args:
            key_ref (str): key reference
            **kwargs (dict) optional values

        Returns:
            str: value or None if not able to parse
        """
        if key_type == "secret":
            return self._resolve_key_type_secret(key_ref, **kwargs)

    def _resolve_key_type_secret(self, key_ref, **kwargs):
        """Resolve key of type "secret".
        Use this function as a custom parser example

        Args:
            key_ref (str): key reference
            **kwargs (dict) optional values

        Returns:
            str: value or False if not able to parse
        """
        if not key_ref:
            return

        # Compose domain used to fetch keys
        #
        # Keys are checked in the following order:
        # 1. Server specific
        # 2. Partner specific
        # 3. General (no server or partner specified)
        server_id = kwargs.get("server_id")
        partner_id = kwargs.get("partner_id")

        key_domain = [
            ("key_ref", "=", key_ref),
            ("server_id", "=", False),
            ("partner_id", "=", False),
        ]

        if server_id:
            key_domain = OR(
                [key_domain, [("key_ref", "=", key_ref), ("server_id", "=", server_id)]]
            )
        if partner_id:
            key_domain = OR(
                [
                    key_domain,
                    [("key_ref", "=", key_ref), ("partner_id", "=", partner_id)],
                ]
            )

        # Fetch keys
        keys = self.search(key_domain).sudo()
        if not keys:
            return

        # Try to get server specific key first
        key = False
        if server_id:
            key = keys.filtered(lambda k: k.server_id.id == server_id)

        # Try to get partner specific key next
        if not key and partner_id:
            key = keys.filtered(lambda k: k.partner_id.id == partner_id)

        if not key:
            # Fallback to a global key
            key = keys

        key_value = key[0].secret_value
        return key_value

    def _replace_with_spoiler(self, code, key_values):
        """Helper function that replaces clean text keys in code with spoiler.
        Eg
        'Code with passwordX and passwordY` will look like:
        'Code with *** and ***'

        Important: this function doesn't parse keys by itself.
        You need to get and provide key values yourself.

        Args:
            code (Text): code to clean
            key_values (List): secret values to be cleaned from code

        Returns:
            Text: cleaned code
        """

        ## No need to search if code is too short
        if not key_values or len(code) <= len(self.KEY_PREFIX) + 3 + len(
            self.KEY_TERMINATOR
        ):  # at least one dot separator and two symbols
            return code

        # Replace keys with values
        for key_value in key_values:
            # Replace key including key terminator
            code = code.replace(key_value, self.SECRET_VALUE_SPOILER)

        return code
