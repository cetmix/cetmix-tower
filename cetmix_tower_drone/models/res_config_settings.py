# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .constants import CRON_BATCH_SIZE_PARAM, DEFAULT_CRON_BATCH_SIZE


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    cetmix_tower_drone_cron_batch_size = fields.Integer(
        string="Drone Cron Batch Size",
        help="Number of jobs the poll and stale pending crons ask controllers "
        "about in one batch. Remaining jobs are handled right after.",
        default=DEFAULT_CRON_BATCH_SIZE,
        config_parameter=CRON_BATCH_SIZE_PARAM,
    )

    @api.constrains("cetmix_tower_drone_cron_batch_size")
    def _check_cetmix_tower_drone_cron_batch_size(self):
        for settings in self:
            if settings.cetmix_tower_drone_cron_batch_size < 1:
                raise ValidationError(
                    self.env._("Drone Cron Batch Size must be at least 1.")
                )
