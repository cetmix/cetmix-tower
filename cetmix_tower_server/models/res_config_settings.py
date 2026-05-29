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
    cetmix_tower_notification_type_error = fields.Selection(
        string="Error Notifications",
        selection=lambda self: self._selection_notifications_type(),
        config_parameter="cetmix_tower_server.notification_type_error",
        help="Type of error notifications",
    )
    cetmix_tower_notification_type_success = fields.Selection(
        string="Success Notifications",
        selection=lambda self: self._selection_notifications_type(),
        config_parameter="cetmix_tower_server.notification_type_success",
        help="Type of success notifications",
    )

    def _selection_notifications_type(self):
        """
        Selection of notifications type
        """
        return [
            ("sticky", _("Sticky")),
            ("non_sticky", _("Non-sticky")),
        ]

    def action_configure_cron_pull_files_from_server(self):
        """
        Configure cron job to pull files from server
        """
        return self._get_cron_job_action(
            "cetmix_tower_server.ir_cron_auto_pull_files_from_server"
        )

    def action_configure_zombie_commands_cron(self):
        """
        Configure cron job to check zombie commands
        """
        return self._get_cron_job_action(
            "cetmix_tower_server.ir_cron_check_zombie_commands"
        )

    def action_configure_run_scheduled_tasks_cron(self):
        """
        Configure cron job to run scheduled tasks
        """
        return self._get_cron_job_action(
            "cetmix_tower_server.ir_cron_run_scheduled_tasks"
        )

    def _get_cron_job_action(self, cron_xml_id):
        """
        Get action to configure cron job
        """
        self.ensure_one()
        cron_id = self.env.ref(cron_xml_id).id
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
