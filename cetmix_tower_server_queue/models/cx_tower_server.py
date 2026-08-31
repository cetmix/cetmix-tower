# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerServer(models.Model):
    _inherit = "cx.tower.server"

    def _get_command_defer_handlers(self):
        """Register the queue_job backend at sequence 50.

        Sequence 10 is reserved for cetmix_tower_drone. The job body
        still calls ``_command_runner`` so routing back through the
        wrapper cannot re-enqueue forever.

        Returns:
            list: ``[(int, callable), ...]`` from ``super()`` plus
                ``(50, self._try_defer_command_queue)``.
        """
        return super()._get_command_defer_handlers() + [
            (50, self._try_defer_command_queue),
        ]

    def _try_defer_command_queue(
        self,
        command,
        log_record,
        rendered_command_code,
        sudo=None,
        rendered_command_path=None,
        ssh_connection=None,
        **kwargs,
    ):
        """Enqueue the command on queue_job when a log record exists.

        Does not enqueue ``jet_action`` / ``create_waypoint`` (those
        complete via their own callbacks). Nested SSH is deferrable.

        Args:
            command (cx.tower.command): Command to run.
            log_record (cx.tower.command.log): Command log, or empty.
            rendered_command_code (str): Rendered command code.
            sudo (str, optional): Command sudo mode.
            rendered_command_path (str, optional): Rendered command path.
            ssh_connection: Ignored; queued jobs always pass None.
            **kwargs: Extra runner arguments.

        Returns:
            bool: True if the command was enqueued, False to try the
                next handler or run in Odoo.
        """
        if not log_record or command.action in ["jet_action", "create_waypoint"]:
            return False
        job = self.with_delay()._queue_command_runner_wrapper(
            command=command,
            log_record=log_record,
            rendered_command_code=rendered_command_code,
            sudo=sudo,
            rendered_command_path=rendered_command_path,
            ssh_connection=None,
            **kwargs,
        )
        log_record.sudo().queue_job_id = job.db_record().id
        return True

    def _queue_command_runner_wrapper(
        self,
        command,
        log_record,
        rendered_command_code,
        sudo=None,
        rendered_command_path=None,
        ssh_connection=None,
        **kwargs,
    ):
        # avoid executing command if plan was stopped
        log_record.invalidate_recordset(["plan_log_id", "finish_date"])
        if log_record.finish_date:
            return
        plan_log_id = log_record.plan_log_id
        if plan_log_id:
            plan_log_id.invalidate_recordset(["is_stopped"])

            # If plan was stopped, stop the command
            if plan_log_id.is_stopped:
                log_record.stop()
                return

        return self._command_runner(
            command=command,
            log_record=log_record,
            rendered_command_code=rendered_command_code,
            sudo=sudo,
            rendered_command_path=rendered_command_path,
            ssh_connection=ssh_connection,
            **kwargs,
        )
