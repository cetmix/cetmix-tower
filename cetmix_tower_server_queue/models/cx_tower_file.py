# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL

_logger = logging.getLogger(__name__)


class CxTowerFile(models.Model):
    _inherit = "cx.tower.file"

    is_being_processed = fields.Boolean(
        copy=False,
        help="File is currently being processed",
    )

    def _check_files_being_processed(self, raise_error):
        """
        Check if any file in the recordset is being processed.
        True if at least one file is already processing and raise_error is False.
        False if no files are currently being processed.
        The caller uses the boolean to decide whether to continue or abort.
        """
        processing_files = self.filtered(lambda rec: rec.is_being_processed)
        if processing_files:
            if raise_error:
                raise UserError(
                    _(
                        "The following files are already being processed: %(name)s",
                        name=", ".join(processing_files.mapped("name")),
                    )
                )
            else:
                return True
        return False

    def _reserve_for_processing(self, raise_error):
        """Claim files that are not already being processed.

        Takes a ``FOR UPDATE`` row lock, re-reads ``is_being_processed``,
        and writes the reservation. The lock is held until this
        transaction commits, so another transaction cannot transfer the
        same file at the same time.

        A concurrent caller does not see the uncommitted flag. It waits
        on the lock, then typically fails with a serialization error
        and is retried by the HTTP layer after this transaction
        commits. Nested calls in this same transaction see the flag
        and abort.

        Args:
            raise_error (bool): If True, raise ``UserError`` when any
                file is already reserved. If False, return True so the
                caller can abort quietly.

        Raises:
            UserError: A file is already reserved and ``raise_error``
                is True.

        Returns:
            bool: True if the caller must abort because a file is busy.
                False if this recordset is now reserved.
        """
        if not self:
            return False
        self.env.cr.execute(
            SQL(
                "SELECT id FROM %s WHERE id IN %s FOR UPDATE",
                SQL.identifier(self._table),
                tuple(self.ids),
            )
        )
        self.invalidate_recordset(["is_being_processed"])
        if self._check_files_being_processed(raise_error):
            return True
        self.write({"server_response": False, "is_being_processed": True})
        return False

    def upload(self, raise_error=False):
        """Upload files in a queue job, or inline in this transaction.

        Without ``inline_file_operation``, enqueue ``_do_upload`` (or
        run it immediately when ``job_uuid`` is already set). With the
        context key, run the core transfer in this transaction while
        holding the row lock.

        Args:
            raise_error (bool): If True, raise when a file is already
                reserved or when the transfer fails. If False, a busy
                non-inline call aborts quietly. Inline transfers always
                raise on failure.

        Context:
            inline_file_operation (bool): When True, run the transfer
                in-process and raise on failure. Used by
                ``file_using_template`` so the command job owns the
                transfer. Does not notify; the command log is the result.
            job_uuid (str): Set by queue_job on the delayed recordset.
                When present, run ``_do_upload`` immediately instead of
                enqueueing another job.

        Raises:
            UserError: A file is already reserved and this call must
                raise, or the file source is incompatible with upload.
            ValidationError: The core transfer failed (inline path).

        Returns:
            str | bool | None: Result of the parent ``upload`` when
                running inline; otherwise None.
        """
        if self._reserve_for_processing(
            raise_error or self.env.context.get("inline_file_operation")
        ):
            return

        if self.env.context.get("inline_file_operation"):
            return self._do_inline_file_operation("upload")

        # Enqueue the upload if not already in a queue job;
        # otherwise, execute immediately
        if not self.env.context.get("job_uuid"):
            self.with_delay()._do_upload(raise_error=raise_error)
        else:
            self._do_upload(raise_error=raise_error)

    def download(self, raise_error=False):
        """Download files in a queue job, or inline in this transaction.

        Without ``inline_file_operation``, enqueue ``_do_download`` (or
        run it immediately when ``job_uuid`` is already set). With the
        context key, run the core transfer in this transaction while
        holding the row lock.

        Args:
            raise_error (bool): If True, raise when a file is already
                reserved or when the transfer fails. If False, a busy
                non-inline call aborts quietly. Inline transfers always
                raise on failure.

        Context:
            inline_file_operation (bool): When True, run the transfer
                in-process and raise on failure. Used by
                ``file_using_template`` so the command job owns the
                transfer. Does not notify; the command log is the result.
            job_uuid (str): Set by queue_job on the delayed recordset.
                When present, run ``_do_download`` immediately instead of
                enqueueing another job.

        Raises:
            UserError: A file is already reserved and this call must
                raise, or the file source is incompatible with download.
            ValidationError: The core transfer failed (inline path).

        Returns:
            str | bool | None: Result of the parent ``download`` when
                running inline; otherwise None.
        """
        if self._reserve_for_processing(
            raise_error or self.env.context.get("inline_file_operation")
        ):
            return

        if self.env.context.get("inline_file_operation"):
            return self._do_inline_file_operation("download")

        # Enqueue the download if not already in a queue job;
        # otherwise, execute immediately
        if not self.env.context.get("job_uuid"):
            self.with_delay()._do_download(raise_error=raise_error)
        else:
            self._do_download(raise_error=raise_error)

    def _do_inline_file_operation(self, operation):
        """Run the core transfer while holding the row lock.

        Used by ``file_using_template`` so the command job owns the
        transfer. Does not notify; the command log is the user-facing
        result. The caller must already have reserved the record via
        ``_reserve_for_processing``.

        A concurrent UI or cron ``upload`` / ``download`` waits on the
        row lock until this transaction commits. It does not see the
        uncommitted ``is_being_processed`` flag. After commit the HTTP
        layer retries and may enqueue its own transfer. Nested calls in
        this same transaction see the flag and do not enqueue.

        Args:
            operation (str): ``upload`` or ``download``.

        Raises:
            UserError: Core refused the transfer (wrong file source).
            ValidationError: Core wrapped an SFTP or process error.

        Returns:
            str | bool | None: Result of the parent ``upload`` or
                ``download`` method.
        """
        try:
            if operation == "upload":
                return super().upload(raise_error=True)
            return super().download(raise_error=True)
        finally:
            self.write({"is_being_processed": False})

    def _do_upload(self, raise_error=True):
        """
        Uploads the files within a job context and notifies the user on success.
        Logs the error if an exception occurs;
        failure state is managed by the parent method.
        """
        try:
            with self.env.cr.savepoint():
                result = super().upload(raise_error=raise_error)
                single_msg = _("File uploaded!")
                plural_msg = _("Files uploaded!")
                self.env.user.notify_success(
                    message=single_msg if len(self) == 1 else plural_msg,
                    title=_("Success"),
                    # This notification should not be sticky
                    # to avoid blocking the user's screen
                    sticky=False,
                )
                return result
        except Exception as e:
            if not raise_error:
                self.env.user.notify_danger(
                    message=_(
                        "File(s) %(name)s upload failed: %(error)s",
                        name=", ".join(self.mapped("name")),
                        error=str(e),
                    ),
                    title=_("Failure"),
                    sticky=self.env["ir.config_parameter"]
                    .sudo()
                    .get_param("cetmix_tower_server.notification_type_error", "sticky")
                    == "sticky",
                )
                _logger.error("File %s upload failed: %s", str(self), str(e))
            else:
                raise
        finally:
            self.write({"is_being_processed": False})

    def _do_download(self, raise_error=True):
        """
        Downloads the files within a job context and notifies the user on success.
        Logs the error if an exception occurs;
        failure state is managed by the parent method.
        """
        try:
            with self.env.cr.savepoint():
                result = super().download(raise_error=raise_error)
                single_msg = _("File downloaded!")
                plural_msg = _("Files downloaded!")
                self.env.user.notify_success(
                    message=single_msg if len(self) == 1 else plural_msg,
                    title=_("Success"),
                    # This notification should not be sticky
                    # to avoid blocking the user's screen
                    sticky=False,
                )
                return result
        except Exception as e:
            if not raise_error:
                self.env.user.notify_danger(
                    message=_(
                        "File(s) %(name)s download failed: %(error)s",
                        name=", ".join(self.mapped("name")),
                        error=str(e),
                    ),
                    title=_("Failure"),
                    sticky=self.env["ir.config_parameter"]
                    .sudo()
                    .get_param("cetmix_tower_server.notification_type_error", "sticky")
                    == "sticky",
                )
                _logger.error("File %s download failed: %s", str(self), str(e))
            else:
                raise
        finally:
            self.write({"is_being_processed": False})

    def action_pull_from_server(self):
        """
        Pull file from server without notification.
        """
        tower_files = self.filtered(lambda file_: file_.source == "tower")
        server_files = self - tower_files

        tower_files.action_get_current_server_code()

        server_files.download(raise_error=False)

    def action_push_to_server(self):
        """
        Push the file to server without success notification.
        """
        server_files = self.filtered(lambda file_: file_.source == "server")
        if server_files:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Failure"),
                    "message": _(
                        "Unable to upload file '%(f)s'.\n"
                        "Upload operation is not supported for 'server' type files.",
                        f=", ".join(server_files.mapped("rendered_name")),
                    ),
                    "sticky": False,
                },
            }

        self.upload(raise_error=False)
