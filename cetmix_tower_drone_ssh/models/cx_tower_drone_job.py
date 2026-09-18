# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models
from odoo.exceptions import UserError

from odoo.addons.cetmix_tower_drone.models.constants import JOB_ACTIVE_STATES

from .constants import SKILL_SSH


class CxTowerDroneJob(models.Model):
    _inherit = "cx.tower.drone.job"

    def _cancel(self):
        """Stop the command logs of the cancelled jobs.

        The callback is not called for a cancelled job, and drone logs are
        left out of the zombie cron, so nothing else would end them.

        Raises:
            UserError: If a log is locked by another transaction and was
                not stopped. The whole cancellation is rolled back then.
        """
        jobs = self.sudo().filtered(lambda j: j.state in JOB_ACTIVE_STATES)
        result = super()._cancel()
        if jobs:
            logs = (
                self.env["cx.tower.command.log"]
                .sudo()
                .search([("drone_job_id", "in", jobs.ids), ("is_running", "=", True)])
            )
            logs.stop()
            # A locked log is skipped by finish() without an error
            logs.invalidate_recordset(["is_running", "finish_date"])
            if logs.filtered("is_running"):
                raise UserError(
                    self.env._(
                        "The command is being updated right now. "
                        "Try to cancel the job again."
                    )
                )
        return result

    def _get_drone_skills(self):
        skills = super()._get_drone_skills()
        skills[SKILL_SSH] = {
            "build_payload": self._drone_skill_ssh_build_payload,
            "get_timeout": self._drone_skill_ssh_get_timeout,
            "get_controller_tags": self._drone_skill_ssh_get_controller_tags,
        }
        return skills

    def _drone_skill_ssh_build_payload(
        self,
        controller,
        server,
        log_record,
        rendered_command_code,
        rendered_command_path=None,
        sudo=None,
        **kwargs,
    ):
        """Build the SSH payload with secrets resolved.

        Runs after the dispatching transaction commits, once per controller
        tried. Exceptions are turned into a rejection of that controller by
        the drone module.

        Args:
            controller (cx.tower.drone.controller): Controller being tried.
            server (cx.tower.server): Server to run the command on.
            log_record (cx.tower.command.log): Command log. Unused.
            rendered_command_code (str): Rendered command code.
            rendered_command_path (str, optional): Rendered command path.
            sudo (str, optional): sudo mode.
            **kwargs: Extra runner arguments. ``key`` is passed to the
                secret parser.

        Returns:
            dict: ``commands``, ``sudo`` and ``connection``.

        Raises:
            ValidationError: If the server host key is missing.
        """
        prepared = server._prepare_ssh_execution(
            rendered_command_code,
            command_path=rendered_command_path,
            sudo=sudo,
            **kwargs,
        )
        return {
            "commands": prepared["commands"],
            "sudo": sudo,
            "connection": server._get_ssh_connection_values(),
        }

    def _drone_skill_ssh_get_timeout(self, **params):
        """Return the core command timeout as the job heartbeat timeout.

        Returns:
            int: Seconds without heartbeat, 0 means no timeout.
        """
        return int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("cetmix_tower_server.command_timeout", 0)
        )

    def _drone_skill_ssh_get_controller_tags(self, server=None, **kwargs):
        """Return the server tags to match controller tags against.

        Args:
            server (cx.tower.server, optional): Server to run the command on.

        Returns:
            cx.tower.tag: Server tags, empty without a server.
        """
        if not server:
            return self.env["cx.tower.tag"]
        return server.tag_ids
