# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models
from odoo.exceptions import ValidationError
from odoo.osv import expression

from odoo.addons.cetmix_tower_server.models.constants import SSH_CONNECTION_ERROR

from .constants import (
    NO_CONTROLLER_POLICY_FAIL,
    NO_CONTROLLER_POLICY_FALLBACK,
    NO_CONTROLLER_POLICY_PARAM,
    NO_DRONE_CONTROLLER,
    SKILL_SSH,
)


class CxTowerServer(models.Model):
    _inherit = "cx.tower.server"

    def _get_command_defer_handlers(self):
        """Register the drone SSH backend at sequence 10."""
        return super()._get_command_defer_handlers() + [
            (10, self._try_defer_command_drone),
        ]

    def _try_defer_command_drone(
        self,
        command,
        log_record,
        rendered_command_code,
        sudo=None,
        rendered_command_path=None,
        ssh_connection=None,
        **kwargs,
    ):
        """Dispatch an SSH command to a drone controller.

        Args:
            command (cx.tower.command): Command to run.
            log_record (cx.tower.command.log): Command log, or empty.
            rendered_command_code (str): Rendered command code.
            sudo (str, optional): Command sudo mode.
            rendered_command_path (str, optional): Rendered command path.
            ssh_connection: Ignored; the drone opens its own connection.
            **kwargs: Extra runner arguments.

        Returns:
            bool: True if the command was taken (dispatched or finished
                with an error), False to try the next handler or run in Odoo.

        Raises:
            ValueError: If Command Timeout is not a number. The command
                run fails.
        """
        if not log_record or command.action != "ssh_command":
            return False

        try:
            prepared = self._prepare_ssh_execution(
                rendered_command_code,
                command_path=rendered_command_path,
                sudo=sudo,
                **kwargs,
            )
            connection = self._get_ssh_connection_values()
        except ValidationError as e:
            log_record.finish(status=SSH_CONNECTION_ERROR, error=str(e))
            return True

        try:
            timeout = int(
                self.env["ir.config_parameter"]
                .sudo()
                .get_param("cetmix_tower_server.command_timeout", 0)
            )
        except (TypeError, ValueError):
            timeout = 0
        if timeout < 0:
            timeout = 0

        job = self.launch_drone(
            SKILL_SSH,
            log_record._on_drone_ssh_done,
            {
                "commands": prepared["commands"],
                "sudo": sudo,
                "connection": connection,
            },
            drone_timeout=timeout,
        )
        if job:
            log_record.sudo().write({"drone_job_id": job.id})
            return True

        policy = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(NO_CONTROLLER_POLICY_PARAM, NO_CONTROLLER_POLICY_FALLBACK)
        )
        if policy != NO_CONTROLLER_POLICY_FAIL:
            return False
        log_record.finish(
            status=NO_DRONE_CONTROLLER,
            error=self.env._("No drone controller is available to run the command"),
        )
        return True

    def _get_zombie_command_log_domain(self, timeout_dt):
        """Leave drone logs to the drone job timeout."""
        return expression.AND(
            [
                super()._get_zombie_command_log_domain(timeout_dt),
                [("drone_job_id", "=", False)],
            ]
        )
