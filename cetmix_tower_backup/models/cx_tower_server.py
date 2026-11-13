# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import models
from odoo.exceptions import ValidationError

from odoo.addons.cetmix_tower_server.models.constants import JET_NOT_FOUND

from .constants import BACKUP_CREATE_FAILED, BACKUP_TEMPLATE_NOT_FOUND


class CxTowerServer(models.Model):
    _inherit = "cx.tower.server"

    def unlink(self):
        """Keep hosts and logs needed by running backup operations.

        Returns:
            bool: Parent unlink result.

        Raises:
            ValidationError: An operation uses one of the source servers.
        """
        if (
            self.env["cx.tower.backup"]
            .sudo()
            .search_count(
                [
                    ("server_id", "in", self.ids),
                    ("state", "in", ["running", "deleting"]),
                ]
            )
        ):
            raise ValidationError(
                self.env._(
                    "A server with a backup operation in progress cannot be deleted."
                )
            )
        return super().unlink()

    def _get_command_runners(self):
        """Register the asynchronous backup command runner.

        Returns:
            dict: Action-to-runner mapping.
        """
        return {
            **super()._get_command_runners(),
            "create_backup": self._command_runner_create_backup,
        }

    def _command_runner_create_backup(self, log_record, **kwargs):
        """Start a backup and let its completion hook finish this command.

        Args:
            log_record (cx.tower.command.log): Triggering command execution.
            **kwargs (dict): Standard runner arguments, unused by this action.

        Returns:
            dict: Status, backup reference response, and error.

        Raises:
            ValidationError: No command log was supplied.
        """
        if not log_record:
            raise ValidationError(
                self.env._("Command log is required for Create Backup commands.")
            )
        jet = log_record.jet_id
        template = log_record.command_id.sudo().backup_template_id
        status = 0
        error = None
        if not jet:
            status, error = (
                JET_NOT_FOUND,
                self.env._("Jet for which command is run is not found."),
            )
        elif not template:
            status, error = (
                BACKUP_TEMPLATE_NOT_FOUND,
                self.env._("Backup Template is not set."),
            )
        else:
            try:
                with self.env.cr.savepoint():
                    backup = (
                        jet.sudo()
                        .with_context(prevent_plan_recursion=True)
                        .create_backup(
                            template,
                            variable_values=log_record.variable_values or {},
                            ignore_busy=True,
                            created_from_command_log=log_record,
                        )
                    )
            except ValidationError:
                status, error = (
                    BACKUP_CREATE_FAILED,
                    self.env._("Backup creation failed."),
                )
            else:
                return {
                    "status": log_record.command_status
                    if not log_record.is_running
                    else 0,
                    "response": {"backup_id": backup.id},
                    "error": log_record.command_error or None,
                }
        log_record.finish(status=status, response=None, error=error)
        return {"status": status, "response": None, "error": error}
