# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import logging

from ansi2html import Ansi2HTMLConverter

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)

html_converter = Ansi2HTMLConverter(inline=True)


class CxTowerServerLog(models.Model):
    """Server log management.
    Used to track various server logs.
    N.B. Do not mistake for command of flight plan log!
    """

    _name = "cx.tower.server.log"
    _inherit = ["cx.tower.access.mixin", "cx.tower.reference.mixin"]
    _description = "Cetmix Tower Server Log"

    NO_LOG_FETCHED_MESSAGE = "<log is empty>"

    active = fields.Boolean(default=True)
    server_id = fields.Many2one("cx.tower.server", ondelete="cascade")
    log_type = fields.Selection(
        selection=lambda self: self._selection_log_type(),
        required=True,
        groups="cetmix_tower_server.group_root,cetmix_tower_server.group_manager",
        default=lambda self: self._selection_log_type()[0][0],
    )
    command_id = fields.Many2one(
        "cx.tower.command",
        domain="[('action', 'in', ['ssh_command', 'python_code']), "
        "'|', ('server_ids', 'in', [server_id]), ('server_ids', '=', False)]",
        groups="cetmix_tower_server.group_root,cetmix_tower_server.group_manager",
        help="Command that will be executed to get the log data.\n"
        "Be careful with commands that don't support parallel execution!",
    )
    use_sudo = fields.Boolean(
        groups="cetmix_tower_server.group_root,cetmix_tower_server.group_manager",
        help="Will use sudo based on server settings."
        "If no sudo is configured will run without sudo",
    )
    file_id = fields.Many2one(
        "cx.tower.file",
        domain="[('server_id', '=', server_id)]",
        groups="cetmix_tower_server.group_root,cetmix_tower_server.group_manager",
        help="File that will be executed to get the log data",
    )
    log_text = fields.Text(readonly=True, copy=False)
    log_html = fields.Html(compute="_compute_log_html")

    # --- Server template related
    server_template_id = fields.Many2one("cx.tower.server.template", ondelete="cascade")
    file_template_id = fields.Many2one(
        "cx.tower.file.template",
        ondelete="cascade",
        groups="cetmix_tower_server.group_root,cetmix_tower_server.group_manager",
        help="This file template will be used to create log files"
        " when server is created from a template",
    )

    def _selection_log_type(self):
        """Actions that can be run by a command.

        Returns:
            List of tuples: available options.
        """
        return [
            ("command", "Command"),
            ("file", "File"),
        ]

    @api.depends("log_text")
    def _compute_log_html(self):
        for record in self:
            if record.log_text:
                try:
                    record.log_html = html_converter.convert(record.log_text)
                # We catch all exceptions to avoid breaking the log display
                except Exception as e:
                    _logger.error("Error converting log text to HTML: %s", e)
                    record.log_html = False
            else:
                record.log_html = False

    def copy(self, default=None):
        return super(
            CxTowerServerLog, self.with_context(reference_mixin_skip_self=True)
        ).copy(default)

    def action_open_log(self):
        """
        Open log record in current window
        """
        self.ensure_one()
        self.action_update_log()
        return {
            "type": "ir.actions.act_window",
            "name": self.name,
            "res_model": "cx.tower.server.log",
            "res_id": self.id,  # pylint: disable=no-member
            "view_mode": "form",
            "target": "current",
        }

    def write(self, vals):
        """Override to protect log_text from direct modifications.
        Bypass with context key 'cx_allow_log_text_update' for internal updates.
        """
        if "log_text" in vals and not self.env.context.get("cx_allow_log_text_update"):
            raise AccessError(_("You are not allowed to modify the server log output."))
        return super().write(vals)

    def action_update_log(self):
        """Update log text from source"""

        # We are using `sudo` to override command/file access limitations
        for rec in self.sudo().with_context(cx_allow_log_text_update=True):
            rec.log_text = rec._get_formatted_log_text()

    def _get_log_text(self):
        """
        Get log text from source
        Use this function to get pure log text from source.

        Returns:
            Text: log text
        """
        self.ensure_one()
        if self.log_type == "file" and self.file_id:
            return self._get_log_from_file()
        elif self.log_type == "command" and self.command_id:
            return self._get_log_from_command()

    def _get_formatted_log_text(self):
        """
        Get formatted log text.
        Use this function to get formatted log text.

        Returns:
            Text: formatted log text
        """
        log_text = self._get_log_text()
        if log_text:
            return self._format_log_text(log_text)
        return self.NO_LOG_FETCHED_MESSAGE

    def _format_log_text(self, log_text):
        """
        Format log text.
        Use this function to format log text.

        Returns:
            Text: formatted log text
        """
        # Remove the null bytes
        return log_text.replace("\x00", "")

    def _get_log_from_file(self):
        """Get log from a file.
        Override this function to implement custom log handler

        Returns:
            Text: log text
        """
        self.ensure_one()
        if self.file_id.source == "server":
            self.file_id.download(raise_error=False)
            return self.file_id.code
        if self.file_id.source == "tower":
            result = self.file_id.action_get_current_server_code()
            if isinstance(result, dict):
                return
            return self.file_id.code_on_server

    def _get_log_from_command(self):
        """Get log from a command.
        Returns:
            Text: log text
        """
        self.ensure_one()

        use_sudo = self.use_sudo and self.server_id.use_sudo
        command_result = self.server_id.with_context(no_command_log=True).run_command(
            self.command_id, sudo=use_sudo
        )
        log_text = self.NO_LOG_FETCHED_MESSAGE
        if command_result:
            response = command_result["response"]
            error = command_result["error"]
            if response:
                log_text = response
            elif error:
                log_text = error
        return log_text

    def _get_copied_name(self, force_name=None):
        # Original name is preserved when log is duplicated
        self.ensure_one()
        return force_name or self.name
