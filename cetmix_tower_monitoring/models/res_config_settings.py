# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    def action_configure_metric_stale_cron(self):
        """
        Configure cron job to check stale metrics
        """
        return self._get_cron_job_action(
            "cetmix_tower_monitoring.ir_cron_cx_tower_metric_value_check_stale"
        )

    def action_configure_metric_pull_data_cron(self):
        """
        Configure cron job that pulls metric data
        """
        return self._get_cron_job_action(
            "cetmix_tower_monitoring.ir_cron_cx_tower_metric_value_pull_data"
        )
