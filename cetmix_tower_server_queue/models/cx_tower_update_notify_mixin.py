# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
"""
Update NOTIFY mixin: send PostgreSQL NOTIFY when configured fields are updated,
and provide wait_for(field, value, timeout) that blocks until the field has the value.

**Important:** wait_for is intended to be used only from within a queue job (e.g. OCA
queue_job). The task that calls wait_for and the task that performs the write and
commit must run in different workers or threads; calling wait_for from a queue job
(which runs in one worker) while another request/worker commits the state change
satisfies this. In test mode, the queue-job requirement is not enforced.

Architecture:
- NOTIFY channel: NOTIFY_CHANNEL (e.g. cx_tower_update).
- Payload: JSON string under 8000 bytes (PostgreSQL limit), e.g.
  {"m": "cx.tower.jet.waypoint", "r": 4498, "f": "state", "v": "ready"}.
- NOTIFY is sent in the same transaction as write(); it is delivered on commit.
- wait_for uses a dedicated connection with autocommit, LISTEN, and blocks with
  select() on the socket. Without NOTIFY on unlink, wait_for does not wake when the
  record is deleted and will time out.
- Dedicated connections are only used inside the function that needs them; the
  cursor is always closed in a ``finally`` block so the connection is returned to
  the pool and never left open after the function returns.

Concrete models set NOTIFY_ON_FIELD_UPDATE to a list of field names to track.
"""
import json
import select
import time

from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

import odoo.sql_db
from odoo import _ as _translate
from odoo import models, tools
from odoo.exceptions import UserError

NOTIFY_CHANNEL = "cx_tower_update"
NOTIFY_PAYLOAD_LIMIT = 8000


class CxTowerUpdateNotifyMixin(models.AbstractModel):
    """
    Mixin: NOTIFY on configured field updates; wait_for(field, value) blocks until
    value.

    Intended for use with queue jobs: call wait_for from a method executed by
    queue_job (e.g. OCA queue_job); the writer (HTTP request or another worker)
    commits the state change, and NOTIFY wakes the waiting job.

    Subclasses must set NOTIFY_ON_FIELD_UPDATE to a list of field names
    (e.g. ["state"]). When any of these fields is written, a PostgreSQL NOTIFY is
    sent per record. wait_for(field, value, timeout) blocks until the field has the
    given value or timeout.
    """

    _name = "cx.tower.update.notify.mixin"
    _description = "Cetmix Tower Update NOTIFY mixin"

    NOTIFY_ON_FIELD_UPDATE = []

    def _notify_field_update(self, record, field, value):
        """Send NOTIFY on the dedicated channel with JSON payload (model, id, field,
        value).

        Args:
            record (BaseModel): A single record (model instance) that was updated.
            field (str): Name of the field that was updated (must be in
                NOTIFY_ON_FIELD_UPDATE).
            value (str | bool | int | float | None): The new value of the field (as
                stored; used in the NOTIFY payload).

        Returns:
            None: Sends NOTIFY via the current cursor; no payload if length >= 8000
            bytes.
        """
        payload = json.dumps(
            {
                "m": record._name,
                "r": record.id,
                "f": field,
                "v": value,
            }
        )
        if len(payload) >= NOTIFY_PAYLOAD_LIMIT:
            return
        # Channel is a fixed identifier; payload is the only parameter.
        self.env.cr.execute(
            "NOTIFY " + NOTIFY_CHANNEL + ", %s",
            (payload,),
        )

    def write(self, vals):
        """Write vals and send NOTIFY for each tracked field in vals (per record).

        Args:
            vals (dict): Dictionary of field names to values to write (standard
                Odoo write).

        Returns:
            bool: Result from super().write(vals) (typically True). NOTIFY is
            skipped when in test mode.

        Raises:
            Whatever super().write(vals) raises (e.g. ValidationError, AccessError).
        """
        result = super().write(vals)
        if self.env.registry.in_test_mode():
            return result
        tracked = [k for k in vals if k in (self.NOTIFY_ON_FIELD_UPDATE or [])]
        if not tracked:
            return result
        payloads = []
        for record in self:
            for field in tracked:
                if field in vals:
                    payload = json.dumps(
                        {
                            "m": record._name,
                            "r": record.id,
                            "f": field,
                            "v": record[field],
                        }
                    )
                    if len(payload) < NOTIFY_PAYLOAD_LIMIT:
                        payloads.append(payload)
        if payloads:
            stmt = "; ".join(["NOTIFY " + NOTIFY_CHANNEL + ", %s"] * len(payloads))
            self.env.cr.execute(stmt, payloads)
        return result

    def _get_wait_for_column(self, field):
        """Return the database column name for `field` on this model (for raw SELECT).

        Args:
            field (str): Field name (must exist on the model; typically from
                NOTIFY_ON_FIELD_UPDATE).

        Returns:
            str: The database column name (e.g. field name or relation column).
        """
        fields_reg = getattr(self, "_fields", None) or {}
        f = fields_reg.get(field)
        if f is None:
            return field
        return getattr(f, "column", None) or field

    def _wait_for_fresh_select(self, listen_cr, field, record_id):
        """Run a fresh SELECT for `field` on record `record_id`; return
        (row_count, value).

        Uses the model table and column (no ORM cache). Used to read committed state
        from a dedicated connection in wait_for.

        Args:
            listen_cr (odoo.sql_db.Cursor): Cursor on the dedicated listen
                connection (e.g. autocommit).
            field (str): Field name to read (must be in NOTIFY_ON_FIELD_UPDATE).
            record_id (int): ID of the record.

        Returns:
            tuple[int, str | bool | int | float | None]: (row_count, value).
            (0, None) if no row (e.g. record deleted); (1, value) if one row; value
            is the raw column value.
        """
        col = self._get_wait_for_column(field)
        table = getattr(self, "_table", None) or ""
        # Identifier quoting: table and column from model/whitelist only
        qry = 'SELECT "{}" FROM "{}" WHERE id = %s'.format(
            col.replace('"', '""'), table.replace('"', '""')
        )
        listen_cr.execute(qry, (record_id,))
        row = listen_cr.fetchone()
        if row is None:
            return 0, None
        return 1, row[0]

    def _wait_for_process_notifies(
        self, raw_conn, listen_cr, model_name, record_id, field, value
    ):
        """Process pending NOTIFYs; return True if value matched, False if no row,
        None to continue."""
        raw_conn.poll()
        notifies = getattr(raw_conn, "notifies", None) or []
        for notify in list(notifies):
            try:
                payload = json.loads(notify.payload)
            except (TypeError, ValueError):
                continue
            if (
                payload.get("m") == model_name
                and payload.get("r") == record_id
                and payload.get("f") == field
            ):
                n, current = self._wait_for_fresh_select(listen_cr, field, record_id)
                if n == 0:
                    return False
                if current == value:
                    return True
        if hasattr(raw_conn, "notifies"):
            raw_conn.notifies = []
        return None

    def wait_for(self, field, value, timeout=60):
        """Block until this record's `field` equals `value` or total timeout.

        **Must be called from within a queue job** (e.g. OCA queue_job). The job's
        target recordset has ``job_uuid`` in context; if it is missing, UserError is
        raised. This ensures the waiter runs in a worker separate from the writer.

        Uses a dedicated DB connection with LISTEN on NOTIFY_CHANNEL; on matching
        NOTIFY runs a fresh SELECT to confirm the value. In test mode, uses a poll
        loop instead of LISTEN and the queue-job check is skipped.
        The dedicated cursor is closed in a ``finally`` block on every exit path so
        the connection is never left open after return.

        Args:
            field (str): Field name; must be in NOTIFY_ON_FIELD_UPDATE (otherwise
                returns False).
            value (str): Expected value; compared to the current DB value (e.g. state
                string).
            timeout (int | float): Total wall-time timeout in seconds (default 60).
                Applies to the whole wait, not per NOTIFY.

        Returns:
            bool: True if the field was observed to equal `value`; False if timeout
            expired, the record no longer exists (no row), or `field` is not
            tracked.

        Raises:
            UserError: If not running inside a queue job (no ``job_uuid`` in
                env.context). wait_for must be called from a method executed by
                queue_job.
            UserError: If the server is running with a single worker (config workers
                == 0). wait_for requires multiple workers so NOTIFY from another
                process can be received. Start Odoo with ``--workers N`` (N >= 1) or
                use test mode.
        """
        if field not in (self.NOTIFY_ON_FIELD_UPDATE or []):
            return False
        self.ensure_one()

        if not self.env.registry.in_test_mode():
            if not self.env.context.get("job_uuid"):
                raise UserError(
                    _translate(
                        "wait_for must be called from within a queue job. "
                        "Use a method executed by queue_job (e.g. OCA queue_job)."
                    )
                )
            if tools.config.get("workers", 0) == 0:
                raise UserError(
                    _translate(
                        "wait_for requires multiple workers (NOTIFY is only "
                        "delivered across processes). Start Odoo with --workers N "
                        "(N >= 1) or use test mode."
                    )
                )

        record_id = self.ids[0]
        model_name = self._name
        dbname = self.env.cr.dbname

        if self.env.registry.in_test_mode():
            return self._wait_for_poll_loop(field, value, timeout, dbname)

        conn = odoo.sql_db.db_connect(dbname)
        listen_cr = conn.cursor()
        try:
            raw_conn = listen_cr._cnx
            raw_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            n, current = self._wait_for_fresh_select(listen_cr, field, record_id)
            if n == 0:
                return False
            if current == value:
                return True
            listen_cr.execute("LISTEN " + NOTIFY_CHANNEL)
            deadline = time.time() + timeout
            while True:
                remaining = max(0, deadline - time.time())
                if remaining <= 0:
                    return False
                try:
                    ready, _, _ = select.select([raw_conn], [], [], min(remaining, 1.0))
                    rlist = list(ready) if ready else []
                except OSError:
                    return False
                if not rlist:
                    continue
                result = self._wait_for_process_notifies(
                    raw_conn, listen_cr, model_name, record_id, field, value
                )
                if result is not None:
                    return result
        finally:
            listen_cr.close()

        return False

    def _wait_for_poll_loop(self, field, value, timeout, dbname):
        """In test mode: poll with fresh SELECT instead of LISTEN (no NOTIFY).

        Used when the registry is in test mode so tests do not depend on commit +
        NOTIFY. Uses a single cursor for the whole loop; runs SELECT each
        iteration, then sleeps. The cursor is closed in a ``finally`` block so the
        connection is returned to the pool when the function returns.

        Args:
            field (str): Field name to wait for (in NOTIFY_ON_FIELD_UPDATE).
            value (str): Expected value.
            timeout (int | float): Total wall-time timeout in seconds.
            dbname (str): Database name (from env.cr.dbname).

        Returns:
            bool: True if the field was observed to equal `value` before timeout;
            False on timeout or if the record no longer exists.
        """
        deadline = time.time() + timeout
        conn = odoo.sql_db.db_connect(dbname)
        listen_cr = conn.cursor()
        try:
            raw_conn = listen_cr._cnx
            raw_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            record_id = self.ids[0]
            while time.time() < deadline:
                n, current = self._wait_for_fresh_select(listen_cr, field, record_id)
                if n == 0:
                    return False
                if current == value:
                    return True
                time.sleep(0.05)
            return False
        finally:
            listen_cr.close()
