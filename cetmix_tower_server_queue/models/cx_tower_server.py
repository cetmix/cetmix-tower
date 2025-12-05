# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class CxTowerServer(models.Model):
    _inherit = "cx.tower.server"

    def _command_runner_wrapper(
        self,
        command,
        log_record,
        rendered_command_code,
        sudo=None,
        rendered_command_path=None,
        ssh_connection=None,
        **kwargs,
    ):
        # If the flight plan log has an entry on the parent flight plan log,
        # it means that this flight plan was launched from another plan,
        # this plan should be launched as a synchronous command to
        # preserve the order of execution of commands with action “Run flight plan”.
        # Use runner only if command log record is provided.
        if log_record and not log_record.plan_log_id.parent_flight_plan_log_id:
            # ssh_connection cannot be serialized for queue jobs and will cause
            # a runtime error. The _queue_command_runner_wrapper will create
            # its own connection if needed (see _command_runner_ssh).
            job = self.with_delay()._queue_command_runner_wrapper(
                command=command,
                log_record=log_record,
                rendered_command_code=rendered_command_code,
                sudo=sudo,
                rendered_command_path=rendered_command_path,
                ssh_connection=None,  # Always None for queued jobs
                **kwargs,
            )
            log_record.sudo().queue_job_id = job.db_record().id

        # Otherwise fallback to `super` to return the command output
        else:
            return super()._command_runner_wrapper(
                command=command,
                log_record=log_record,
                rendered_command_code=rendered_command_code,
                sudo=sudo,
                rendered_command_path=rendered_command_path,
                ssh_connection=ssh_connection,
                **kwargs,
            )

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
        log_record.invalidate_recordset(["plan_log_id"])
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
