from collections import defaultdict

from odoo import api, models


class CxTowerVaultMixin(models.AbstractModel):
    """Mixin for vault functionality.

    This mixin provides methods to securely store and retrieve sensitive data
    in the vault. Inheriting models must define SECRET_FIELDS list with field
    names that should be stored in the vault.
    """

    _name = "cx.tower.vault.mixin"
    _description = "Cetmix Tower Vault Mixin"

    SECRET_VALUE_PLACEHOLDER = "*****"
    SECRET_FIELDS = []

    def _fetch_query(self, query, fields):
        """Substitute fields based on api.

        This method replaces values of secret fields with a placeholder value
        when they are read from the database.

        Args:
            query (str): Query to fetch records
            fields (list): List of fields to read
        """
        records = super()._fetch_query(query, fields)

        # Replace secret field values with placeholders
        for secret_field in self.SECRET_FIELDS:
            if not fields or secret_field in [f.name for f in fields]:
                # Use cache to set placeholder values without triggering field access
                for record in records:
                    field = self._fields[secret_field]
                    self.env.cache.set(record, field, self.SECRET_VALUE_PLACEHOLDER)
        return records

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to handle secret values securely.

        Extracts secret fields, stores them in vault, and prevents
        actual secret values from being saved in the main table.

        Args:
            vals_list (list): List of dictionaries containing field values
                             for record creation

        Returns:
            recordset: Created records with secret values stored in vault

        Note:
            Secret fields are automatically processed and stored securely.
            The main database table never contains actual secret values.
        """

        # Step 1: Extract secret fields and generate temporary IDs
        secret_vals = self._extract_and_replace_secret_fields(vals_list)

        # Step 2: Create records with batch operation
        records = super().create(vals_list)

        # Step 3: Update vault records with real IDs
        if secret_vals:
            self._process_secret_values_after_creation(records, secret_vals)

        return records

    def write(self, vals):
        """Override write to handle secret fields.

        Extracts secret field values from vals dictionary and stores them securely
        in the vault instead of the main database table. The remaining non-secret
        fields are processed by the standard write method.

        Args:
            vals (dict): Dictionary of field values to write to records

        Returns:
            bool: Result of the parent write operation

        Note:
            Secret fields defined in SECRET_FIELDS are automatically intercepted
            and stored in vault. Cache is invalidated for all secret fields when
            any secret field is modified.
        """
        # Extract secret fields
        secret_values = {}
        for secret_field in self.SECRET_FIELDS:
            if secret_field in vals:
                secret_values[secret_field] = vals.pop(secret_field)

        res = super().write(vals)

        if secret_values:
            self._set_secret_values(secret_values)
            # Invalidate cache for all secret fields
            self.invalidate_recordset(self.SECRET_FIELDS)

        return res

    def unlink(self):
        """Override unlink to delete vault records.

        Automatically removes all associated vault records after deleting
        the main records to prevent orphaned secret data in the vault.

        Returns:
            bool: Result of the parent unlink operation

        Note:
            Vault cleanup is performed automatically and cannot be bypassed.
        """
        ids = self.ids

        res = super().unlink()

        # Find all vault records for these records
        vault_records = (
            self.env["cx.tower.vault"]
            .sudo()
            .search([("res_model", "=", self._name), ("res_id", "in", ids)])
        )

        # Delete vault records
        if vault_records:
            vault_records.sudo().unlink()

        return res

    def _get_secret_value(self, field_name):
        """Retrieves the actual secret value for a specific field for a single record.

        This method is the only way to get the real secret field value because:
        - Direct field access (e.g., self.secret_field)
          returns placeholder due to _read() override
        - The actual field in the main table is empty/NULL
          as values are stored in vault

        Args:
            field_name (str): Name of the secret field to retrieve

        Returns:
            str or None: The actual secret value, or None if not found or field
                        is not in SECRET_FIELDS

        Note:
            This method bypasses Odoo's ORM field access to avoid getting
            placeholder values returned by the overridden _read() method.
        """

        self.ensure_one()

        return self._get_secret_values([field_name]).get(self.id, {}).get(field_name)

    def _get_secret_values(self, fields_list=None):
        """Retrieve secret values from the vault for specified fields.

        This method fetches secret values stored in the vault for all records
        in the current recordset and specified fields (or all SECRET_FIELDS).

        Args:
            fields_list (list, optional): List of field names to retrieve.
                                        Defaults to all SECRET_FIELDS.

        Returns:
            dict: Dictionary mapping record IDs to their secret field values.
                  Structure: {res_id: {field_name: secret_value}}

                  Example:
                  {1: {'ssh_password': 'secret123', 'host_key': 'key456'},
                   2: {'ssh_password': 'secret789'}}

        Note:
            This method searches vault records using standard domain filtering
            by res_id, and field_name for reliable record matching.
            If a record has no secret values this record is not included in the result.
        """
        # If no records, return empty dict
        if not self:
            return {}

        # Prepare fields to fetch
        fields_to_fetch = (
            [f for f in fields_list if f in self.SECRET_FIELDS]
            if fields_list
            else self.SECRET_FIELDS
        )
        # If no fields to fetch, return empty dict
        if not fields_to_fetch:
            return {}

        # Search vault records for all records and all secret fields
        domain = [
            ("res_model", "=", self._name),
            ("res_id", "in", self.ids),
            ("field_name", "in", fields_to_fetch),
        ]
        vault_records = (
            self.env["cx.tower.vault"]
            .sudo()
            .search_read(
                domain,
                ["res_id", "field_name", "data"],
            )
        )
        res = defaultdict(dict)
        for record in vault_records:
            res[record["res_id"]][record["field_name"]] = record["data"]

        return dict(res)

    def _set_secret_values(self, vals):
        """Store secret values in the vault.

        This method stores sensitive data in the vault for all records in the recordset.
        It either updates existing vault records or creates new ones for each
        record-field pair in the vals dictionary.

        This method can be overridden to implement custom storage mechanisms
        for secret values, such as external key management systems or
        encryption services.

        Args:
            vals (dict): Dictionary mapping field names to their secret values
                         to be stored in the vault for all records

        Returns:
            None
        """
        if not vals or not self:
            return

        # Get all existing vault records in ONE SQL query
        domain = [
            ("res_model", "=", self._name),
            ("res_id", "in", self.ids),
            ("field_name", "in", list(vals.keys())),
        ]
        existing_vault_records = self.env["cx.tower.vault"].sudo().search(domain)

        # Prepare data for batch operations
        vals_to_update_records = defaultdict(lambda: self.env["cx.tower.vault"])
        records_to_unlink = self.env["cx.tower.vault"]
        records_to_create = []

        # Index existing records by (res_id, field_name) for O(1) lookups
        existing_map = {(v.res_id, v.field_name): v for v in existing_vault_records}

        # Only allow known secret fields to be set
        allowed_fields = set(self.SECRET_FIELDS)

        # Process each record and field combination
        for record in self:
            for field, value in vals.items():
                if field not in allowed_fields:
                    continue
                # Fast lookup for existing record
                existing_record = existing_map.get((record.id, field))
                if existing_record:
                    if value is False or value is None:
                        records_to_unlink |= existing_record
                    else:
                        vals_to_update_records[value] |= existing_record

                else:
                    if value is False or value is None:
                        continue

                    records_to_create.append(
                        {
                            "res_model": self._name,
                            "res_id": record.id,
                            "field_name": field,
                            "data": value,
                        }
                    )

        # Batch operations
        for value, records in vals_to_update_records.items():
            records.sudo().write({"data": value})

        if records_to_create:
            self.env["cx.tower.vault"].sudo().create(records_to_create)
        if records_to_unlink:
            records_to_unlink.sudo().unlink()

    def _extract_and_replace_secret_fields(self, vals_list):
        """Extract secret fields and replace with temporary identifiers.

        Processes value dictionaries for record creation, replacing secret field values
        with unique temporary identifiers. The actual secret values are mapped to these
        temporary identifiers for later secure storage in the vault system.

        Args:
            vals_list (list): List of value dictionaries for record creation.

         Returns:
           dict: Mapping of temporary identifiers to secret values.
            Note: vals_list is modified in-place to contain temp identifiers.

        Note:
            Used during record creation as part of the secure secret storage workflow.
        """
        temp_id_counter = 0
        secret_vals = {}

        for vals in vals_list:
            for secret_field in self.SECRET_FIELDS:
                if (
                    secret_field in vals
                    and vals[secret_field] is not False
                    and vals[secret_field] is not None
                ):
                    temp_id_counter += 1
                    temp_identifier = str(temp_id_counter)
                    secret_vals[temp_identifier] = vals[secret_field]
                    vals[secret_field] = temp_identifier

        return secret_vals

    def _process_secret_values_after_creation(self, records, secret_vals):
        """Process secret values after records creation.

        Replaces temporary identifiers with actual secret values in the vault
        and invalidates cache for affected fields.

        Args:
            records (recordset): Newly created records with temporary identifiers
            secret_vals (dict): Mapping of temporary identifiers to secret values

        Returns:
            None

        Note:
            Called automatically during create() process. Should not be used directly.
        """
        fields_str = ", ".join(self.SECRET_FIELDS)
        query = f"SELECT id, {fields_str} FROM {self._table} WHERE id in %s"
        self.env.cr.execute(query, (tuple(records.ids),))
        records_dict = self.env.cr.dictfetchall()

        for record_dict in records_dict:
            self._process_single_record_secrets(record_dict, secret_vals)

        records._clear_temp_values()
        records.invalidate_recordset(self.SECRET_FIELDS)

    def _process_single_record_secrets(self, record_dict, secret_vals):
        """Process secrets for a single record.

        Replaces temporary identifiers with actual secret values for one record,
        clears temporary values from main table and stores secrets in vault.

        Args:
            record_dict (dict): Dictionary with record data
            including temporary identifiers
            secret_vals (dict): Mapping of temporary identifiers to actual secret values

        Returns:
            None

        Note:
            Internal method used by _process_secret_values_after_creation.
        """
        record_id = record_dict.get("id")
        vault_vals = {}
        field_temp_id_pairs = (
            (field_name, record_dict[field_name]) for field_name in self.SECRET_FIELDS
        )

        # Collect secret values and fields to clear
        for field_name, temp_identifier in field_temp_id_pairs:
            secret_value = secret_vals.get(temp_identifier)
            if secret_value:
                vault_vals[field_name] = secret_value

        # Update database and vault if needed
        if vault_vals:
            record = self.browse(record_id)
            record._set_secret_values(vault_vals)

    def _clear_temp_values(self):
        """Clear temporary values from main table.

        Sets all SECRET_FIELDS to NULL in the database to remove temporary
        identifiers after secret values have been stored in vault.
        Works with multiple records in the recordset.

        Returns:
            None

        Note:
            Internal method used during secret processing workflow.
            Clears all SECRET_FIELDS for all records in the current recordset.
        """
        set_clause = ", ".join(f"{field} = NULL" for field in self.SECRET_FIELDS)
        query = f"UPDATE {self._table} SET {set_clause} WHERE id in %s"
        self.env.cr.execute(query, (tuple(self.ids),))
