from odoo import _, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    """
    Inherit res.config.settings to add new settings
    """

    _inherit = "res.config.settings"

    def action_configure_cron(self):
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
            "name": _("Pull Files from Server"),
            "views": [(False, "form")],
            "res_model": "ir.cron",
            "res_id": cron_id,
            "type": "ir.actions.act_window",
            "target": "new",
        }
