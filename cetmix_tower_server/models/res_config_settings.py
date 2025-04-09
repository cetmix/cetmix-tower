from odoo import _, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    """
    Inherit res.config.settings to add new settings
    """

    _inherit = "res.config.settings"

    cetmix_tower_command_timeout = fields.Integer(
        string="Command Timeout",
        config_parameter="cetmix_tower_server.command_timeout",
        help="Timeout for commands in seconds after which"
        " the command will be terminated",
    )

    def action_configure_cron_pull_files_from_server(self):
        """
        Configure cron job to pull files from server
        """
        self.ensure_one()
        cron_id = self.env.ref(
            "cetmix_tower_server.ir_cron_auto_pull_files_from_server"
        ).id
        if not cron_id:
            raise ValidationError(_("Cron job not found"))
        return {
            "name": _("Cron Job"),
            "views": [(False, "form")],
            "res_model": "ir.cron",
            "res_id": cron_id,
            "type": "ir.actions.act_window",
            "target": "new",
        }

    def action_configure_zombie_commands_cron(self):
        """
        Configure cron job to check zombie commands
        """
        self.ensure_one()
        cron_id = self.env.ref("cetmix_tower_server.ir_cron_check_zombie_commands").id
        if not cron_id:
            raise ValidationError(_("Cron job not found"))
        return {
            "name": _("Cron Job"),
            "views": [(False, "form")],
            "res_model": "ir.cron",
            "res_id": cron_id,
            "type": "ir.actions.act_window",
            "target": "new",
        }
