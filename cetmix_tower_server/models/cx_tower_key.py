# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID, api, fields, models


class CxTowerKey(models.Model):
    """SSH Private key and secret storage"""

    _name = "cx.tower.key"
    _description = "Cetmix Tower Key/Secret Storage"
    _inherit = ["cx.tower.reference.mixin", "cx.tower.access.role.mixin"]
    _order = "name"

    KEY_PREFIX = "#!cxtower"
    KEY_TERMINATOR = "!#"
    SECRET_VALUE_PLACEHOLDER = "*** Insert new value to replace the existing one ***"
    SECRET_VALUE_SPOILER = "*****"

    key_type = fields.Selection(
        selection=[
            ("k", "SSH Key"),
            ("s", "Secret"),
        ],
        required=True,
    )
    reference_code = fields.Char(
        compute="_compute_reference_code",
        help="Key reference for inline usage",
    )
    secret_value = fields.Text(
        string="SSH Private Key",
        compute="_compute_secret_value",
        inverse="_inverse_secret_value",
        store=True,
    )
    value_ids = fields.One2many(
        string="Values",
        comodel_name="cx.tower.key.value",
        inverse_name="key_id",
    )
    server_ssh_ids = fields.One2many(
        string="Used as SSH Key",
        comodel_name="cx.tower.server",
        inverse_name="ssh_key_id",
        readonly=True,
        help="Used as SSH key in the following servers",
    )
    note = fields.Text()

    # ---- Access. Add relation for mixin fields
    user_ids = fields.Many2many(
        relation="cx_tower_key_user_rel",
        domain=lambda self: [
            ("groups_id", "in", [self.env.ref("cetmix_tower_server.group_manager").id])
        ],
    )
    manager_ids = fields.Many2many(
        relation="cx_tower_key_manager_rel",
    )

    @api.depends("reference", "key_type")
    def _compute_reference_code(self):
        """Compute key reference
        Eg '#!cxtower.secret.KEY!#'
        """
        for rec in self:
            if rec.reference:
                key_prefix = self._compose_key_prefix(rec.key_type)
                if key_prefix:
                    rec.reference_code = f"#!cxtower.{key_prefix}.{rec.reference}!#"
                else:
                    rec.reference_code = None
            else:
                rec.reference_code = None

    @api.depends(
        "key_type",
        "value_ids",
        "value_ids.secret_value",
        "value_ids.server_id",
        "value_ids.partner_id",
    )
    def _compute_secret_value(self):
        for rec in self:
            if rec.key_type == "s":
                # General value
                general_value = rec.value_ids.filtered(lambda x: not x.server_id)
                if general_value:
                    rec.secret_value = (
                        general_value[0].with_user(SUPERUSER_ID).secret_value
                    )
                else:
                    rec.secret_value = None

    def _inverse_secret_value(self):
        key_value_obj = self.env["cx.tower.key.value"]
        for rec in self:
            if rec.key_type == "s" and rec.secret_value:
                # General value
                general_value = rec.value_ids.filtered(
                    lambda x: not x.server_id and not x.partner_id and x.id
                )
                if general_value:
                    general_value.secret_value = rec.with_user(
                        SUPERUSER_ID
                    ).secret_value
                else:
                    key_value_obj.create(
                        {
                            "key_id": rec.id,
                            "secret_value": rec.secret_value,
                        }
                    )

    def write(self, vals):
        res = super().write(vals)
        if "secret_value" in vals:
            self.invalidate_recordset(["secret_value"])
        return res

    def _get_reference_pattern(self):
        """
        Override mixin method
        """
        return "[a-zA-Z0-9_]"

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

    def _read(self, fields):  # pylint: disable=missing-return # doesn't return anything
        """Substitute fields based on api"""
        super()._read(fields)
        if not self.env.user._is_superuser() and (
            "secret_value" in fields or fields == []
        ):
            # Public user used for substitution
            for record in self:
                try:
                    record._cache["secret_value"] = self.SECRET_VALUE_PLACEHOLDER
                except Exception:  # pylint: disable=except-pass
                    # skip SpecialValue
                    # (e.g. for missing record or access right)
                    pass

    def _parse_code_and_return_key_values(self, code, pythonic_mode=False, **kwargs):
        """Replaces key placeholders in code with the corresponding values,
        returning key values.

        This function is meant to be used in the flow where key values
        are needed for some follow up operations such as command log clean up.

        NB:
        - key format must follow "#!cxtower.key.KEY_ID!#" pattern.
            eg #!cxtower.secret.GITHUB_TOKEN!# for GITHUB_TOKEN key
        Args:
            code (Text): code to process
            pythonic_mode (Bool): If True, all variables in kwargs are converted to
                                  strings and wrapped in double quotes.
                                  Default is False.
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
                if pythonic_mode:
                    # save key value as string in pythonic mode
                    key_value = f'"{key_value}"'
                    # Escape newline characters to ensure the key value remains
                    # a valid single-line string. This prevents syntax errors
                    # when the string is used in contexts where unescaped
                    # newlines would break Python syntax or evaluation logic.
                    key_value = key_value.replace("\n", "\\n")

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
            code (Text): description
            **kwargs (dict): optional arguments
        Returns:
            [str]: list of key strings
        """
        key_strings = []
        key_terminator_len = len(self.KEY_TERMINATOR)
        index_from = 0  # initial position

        while index_from >= 0:
            index_from = code.find(self.KEY_PREFIX, index_from)
            if index_from >= 0:
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
                    # No terminator found, move past this occurrence of prefix
                    index_from += len(self.KEY_PREFIX)
            else:
                # No more prefixes found
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

        key_parts = self._extract_key_parts(key_string)
        if key_parts is None:
            return None

        key_type, reference = key_parts
        key_value = self._resolve_key(key_type, reference, **kwargs)

        return key_value

    def _extract_key_parts(self, key_string):
        """Extract and validate key parts from the key string.

        Args:
            key_string (str): key string

        Returns:
            tuple: (key_type, reference) if valid, else None
        """
        key_parts = (
            key_string.replace(" ", "").replace(self.KEY_TERMINATOR, "").split(".")
        )

        # Must be 3 parts including pre!
        if len(key_parts) == 3 and key_parts[0] == self.KEY_PREFIX:
            return key_parts[1], key_parts[2]

        return None

    def _resolve_key(self, key_type, reference, **kwargs):
        """Resolve key
        Inherit this function to implement your own resolvers

        Args:
            reference (str): key reference
            **kwargs (dict) optional values

        Returns:
            str: value or None if not able to parse
        """
        if key_type == "secret":
            return self._resolve_key_type_secret(reference, **kwargs)

    def _resolve_key_type_secret(self, reference, **kwargs):
        """Resolve key of type "secret".
        Use this function as a custom parser example

        Args:
            reference (str): key reference
            **kwargs (dict) optional values

        Returns:
            str: value or False if not able to parse
        """
        if not reference:
            return

        # Compose domain used to fetch keys
        #
        # Keys are checked in the following order:
        # 1. Partner and Server specific
        # 2. Server specific
        # 3. Partner specific
        # 4. General (no server or partner specified)
        server_id = kwargs.get("server_id")
        partner_id = kwargs.get("partner_id")

        # Fetch key
        key = self.sudo().search([("reference", "=", reference)], limit=1)
        if not key:
            return

        # Check if key has custom values
        key_values = key.value_ids
        key_value = None

        # 1. Server and Partner specific key first
        if key_values and server_id and partner_id:
            filtered_key_values = key_values.filtered(
                lambda k: k.server_id.id == server_id and k.partner_id.id == partner_id
            )
            if filtered_key_values:
                key_value = filtered_key_values[0]

        # 2. Server specific key first
        if not key_value and key_values and server_id:
            filtered_key_values = key_values.filtered(
                lambda k: k.server_id.id == server_id and not k.partner_id
            )
            if filtered_key_values:
                key_value = filtered_key_values[0]

        # 3. Partner specific key next
        if not key_value and key_values and partner_id:
            filtered_key_values = key_values.filtered(
                lambda k: k.partner_id.id == partner_id and not k.server_id
            )
            if filtered_key_values:
                key_value = filtered_key_values[0]

        # 4. General key next
        if not key_value and key_values:
            filtered_key_values = key_values.filtered(
                lambda k: not k.partner_id and not k.server_id
            )
            if filtered_key_values:
                key_value = filtered_key_values[0]

        if key_value:
            return key_value._get_secret_value()

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

        if not key_values:
            return code

        # Replace keys with values
        for key_value in key_values:
            # If key_value includes quotes, remove them for the replacement
            key_value = key_value.strip('"')
            # If key_value contains an escaped line break replace then remove escaping
            key_value = key_value.replace("\\n", "\n")
            # Replace key including key terminator
            code = code.replace(key_value, self.SECRET_VALUE_SPOILER)

        return code

    def _get_secret_value(self):
        """Get secret value.
        Override this method in case you need
        to implement custom key storages.

        Returns:
            str: secret value or None if no secret value is found
        """

        # Return None in case of empty recordset
        if not self:
            return
        self.env.cr.execute(
            """
            SELECT secret_value
            FROM cx_tower_key
            WHERE id = %s
            """,
            [self.id],
        )
        result = self.env.cr.fetchone()
        if result:
            return result[0]
