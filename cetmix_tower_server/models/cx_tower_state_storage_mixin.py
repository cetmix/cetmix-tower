# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import odoo.sql_db
from odoo import api, fields, models


def _read_from_state_storage_default(record, fields_list):
    """
    Read the given fields from the record's table via a new connection
    (so committed values from other workers are visible).
    """
    table = record._table
    dbname = record.env.cr.dbname
    columns = ", ".join(f'"{f}"' for f in fields_list)
    with odoo.sql_db.db_connect(dbname).cursor() as cr:
        cr.execute(
            f'SELECT {columns} FROM "{table}" WHERE id = %s',
            (record.id,),
        )
        row = cr.fetchone()
    return list(row) if row else None


def _get_storage_value(record, field_name):
    """Get value for one field from state storage; use mixin or default."""
    if hasattr(record, "_read_from_state_storage"):
        row = record._read_from_state_storage([field_name])
        if row is not None:
            return row[0]
    row = _read_from_state_storage_default(record, [field_name])
    return row[0] if row else False


class StateStorageSelection(fields.Selection):
    """
    Selection field that reads from state storage when context has
    ``read_from_state_storage`` set (e.g. in Python commands polling
    another worker).

    Use with :class:`CxTowerStateStorageMixin` for write path; override
    the mixin's _read_from_state_storage / _write_to_state_storage
    for custom storage.
    """

    def __get__(self, record, owner):
        if record is not None and record._ids:
            record.ensure_one()
            if (
                not record.env.context.get("cetmix_tower_test_mode")
                and not record.env.registry.in_test_mode()
                and record.env.context.get("read_from_state_storage")
            ):
                value = _get_storage_value(record, self.name)
                cache_val = self.convert_to_cache(value, record, validate=False)
                return self.convert_to_record(cache_val, record)
        return super().__get__(record, owner)


class StateStorageChar(fields.Char):
    """
    Char field that reads from state storage when context has
    ``read_from_state_storage`` set (e.g. in Python commands polling
    another worker).

    Use with :class:`CxTowerStateStorageMixin` for write path; override
    the mixin's _read_from_state_storage / _write_to_state_storage
    for custom storage.
    """

    def __get__(self, record, owner):
        if record is not None and record._ids:
            record.ensure_one()
            if (
                not record.env.context.get("cetmix_tower_test_mode")
                and record.env.context.get("read_from_state_storage")
                and not record.env.registry.in_test_mode()
            ):
                value = _get_storage_value(record, self.name)
                cache_val = self.convert_to_cache(value, record, validate=False)
                return self.convert_to_record(cache_val, record)
        return super().__get__(record, owner)


class CxTowerStateStorageMixin(models.AbstractModel):
    """Mixin for models using state-storage fields: centralizes read/write.

    Models using :class:`StateStorageSelection` or :class:`StateStorageChar`
    should inherit this mixin. It hooks create/write/unlink to sync those
    fields via _write_to_state_storage / _delete_from_state_storage.
    Override the methods below in custom code to implement an external store
    (e.g. Redis, dedicated table); on read failure, the field falls back to
    the main table when _read_from_state_storage returns None.

    Overridable methods:
    - _read_from_state_storage(self, fields_list) -> list of values or None
    - _write_to_state_storage(self, values)  # values: dict {field_name: value}
    - _delete_from_state_storage(self)
    """

    _name = "cx.tower.state.storage.mixin"
    _description = "Cetmix Tower State Storage Mixin"

    def _get_state_storage_field_names(self):
        """Return field names that use StateStorageSelection or StateStorageChar."""
        return [
            name
            for name, field in self._fields.items()
            if isinstance(field, StateStorageSelection | StateStorageChar)
        ]

    def _read_from_state_storage(self, fields_list):
        """
        Read the given fields from state storage for this record.

        Default: model's table via a new connection (committed data visible
        to other workers). Override to use an external store; return None on
        failure to fall back to main table.

        :param fields_list: list of field names to read
        :return: list of values in same order as fields_list, or None
        """
        return _read_from_state_storage_default(self, fields_list)

    def _write_to_state_storage(self, values):
        """
        Write the given field values to state storage for this record.

        Default: no-op (ORM already wrote to main table). Override to
        also write to an external store (e.g. Redis, dedicated table)
        for cross-worker visibility.

        :param values: dict {field_name: value} to persist
        """
        # Default: main table is updated by ORM; override for external store
        pass

    def _delete_from_state_storage(self):
        """
        Remove this record's state from storage (e.g. on unlink).

        Default: no-op. Override when using an external store that
        must be cleaned up.
        """
        pass

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if records and not self.env.registry.in_test_mode():
            storage_fields = self._get_state_storage_field_names()
            if storage_fields:
                if isinstance(vals_list, dict):
                    vals_list = [vals_list]
                for rec, vals in zip(records, vals_list, strict=True):
                    vals_storage = {
                        k: v for k, v in vals.items() if k in storage_fields
                    }
                    if vals_storage:
                        rec._write_to_state_storage(vals_storage)
        return records

    def write(self, vals):
        result = super().write(vals)
        if result and not self.env.registry.in_test_mode():
            storage_fields = self._get_state_storage_field_names()
            vals_storage = {k: v for k, v in vals.items() if k in storage_fields}
            if vals_storage:
                for rec in self:
                    rec._write_to_state_storage(vals_storage)
        return result

    def unlink(self):
        if not self.env.registry.in_test_mode():
            for rec in self:
                rec._delete_from_state_storage()
        return super().unlink()
