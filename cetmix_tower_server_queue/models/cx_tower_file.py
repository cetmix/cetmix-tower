# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

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

    def upload(self, raise_error=False):
        """
        Trigger asynchronous upload via job queue.
        """
        # Check if the file is already being processed
        if self._check_files_being_processed(raise_error):
            return

        self.write({"server_response": False, "is_being_processed": True})

        # Enqueue the upload if not already in a queue job;
        # otherwise, execute immediately
        if not self.env.context.get("job_uuid"):
            self.with_delay()._do_upload(raise_error=raise_error)
        else:
            self._do_upload(raise_error=raise_error)

    def download(self, raise_error=False):
        """
        Trigger asynchronous download via job queue.
        """

        # Check if the file is already being processed
        if self._check_files_being_processed(raise_error):
            return

        self.write({"server_response": False, "is_being_processed": True})

        # Enqueue the download if not already in a queue job;
        # otherwise, execute immediately
        if not self.env.context.get("job_uuid"):
            self.with_delay()._do_download(raise_error=raise_error)
        else:
            self._do_download(raise_error=raise_error)

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
