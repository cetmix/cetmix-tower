# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, fields, models
from odoo.tools import plaintext2html


class CxTowerServerLog(models.Model):
    """Server log management.
    Used to track various server logs.
    N.B. Do not mistake for command of flight plan log!
    """

    _name = "cx.tower.server.log"
    _inherit = ["cx.tower.access.mixin"]
    _description = "Cetmix Tower Server Log"

    NO_LOG_FETCHED_MESSAGE = _("<log is empty>")

    def _selection_log_type(self):
        """Actions that can be run by a command.

        Returns:
            List of tuples: available options.
        """
        return [
            ("command", "Command"),
            ("file", "File"),
        ]

    active = fields.Boolean(default=True)
    name = fields.Char(required=True)
    server_id = fields.Many2one("cx.tower.server", ondelete="cascade")
    log_type = fields.Selection(
        selection=lambda self: self._selection_log_type(),
        required=True,
        groups="cetmix_tower_server.group_root,cetmix_tower_server.group_manager",
        default=lambda self: self._selection_log_type()[0][0],
    )
    command_id = fields.Many2one(
        "cx.tower.command",
        domain="['|', ('server_ids', 'in', [server_id]), ('server_ids', '=', False)]",  # noqa
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
    log_text = fields.Html(readonly=True)

    # --- Server template related
    server_template_id = fields.Many2one("cx.tower.server.template", ondelete="cascade")
    file_template_id = fields.Many2one(
        "cx.tower.file.template",
        ondelete="cascade",
        groups="cetmix_tower_server.group_root,cetmix_tower_server.group_manager",
        help="This file template will be used to create log files"
        " when server is created from a template",
    )

    def _format_log_text(self, log_text):
        """Formats log text to prior to display it.
        Override this function to implement custom log formatting.

        Args:
            log_text (Text): source log text

        Returns:
            Html: formatted log text
        """
        return plaintext2html(log_text)

    def action_open_log(self):
        """
        Open log record in current window
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.name,
            "res_model": "cx.tower.server.log",
            "res_id": self.id,  # pylint: disable=no-member
            "view_mode": "form",
            "view_type": "form",
            "target": "current",
        }

    def action_get_log_text(self):
        """Update log text from source"""

        # We are using `sudo` to override command/file access limitations
        for rec in self.sudo():
            if rec.log_type == "file" and rec.file_id:
                log_text = rec._get_log_from_file()
            elif rec.log_type == "command" and rec.command_id:
                log_text = rec._get_log_from_command()
            else:
                log_text = self.NO_LOG_FETCHED_MESSAGE
            rec.log_text = self._format_log_text(log_text)

    def _get_log_from_file(self):
        """Get log from a file.
        Override this function to implement custom log handler

        Returns:
            Text: log text. Supports HTML formatting
        """
        self.ensure_one()
        if self.file_id.source == "server":
            return self.file_id.code
        if self.file_id.source == "tower":
            return self.file_id.code_on_server

    def _get_log_from_command(self):
        """Get log from a command.
        Returns:
            Text: log text. Supports HTML formatting
        """
        self.ensure_one()

        use_sudo = self.use_sudo and self.server_id.use_sudo
        command_result = self.server_id.with_context(no_log=True).execute_command(
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
