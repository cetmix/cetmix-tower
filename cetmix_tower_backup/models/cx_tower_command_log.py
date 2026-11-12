# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class CxTowerCommandLog(models.Model):
    _inherit = "cx.tower.command.log"

    has_backup_values = fields.Boolean(
        readonly=True, index=True, groups="cetmix_tower_base.group_root"
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Inherit backup provenance even after Python rewrites custom values.

        Args:
            vals_list (list[dict]): Initial command-log values.

        Returns:
            cx.tower.command.log: Created command logs.
        """
        plans = (
            self.env["cx.tower.plan.log"]
            .sudo()
            .browse(
                [vals["plan_log_id"] for vals in vals_list if vals.get("plan_log_id")]
            )
        )
        protected = set(plans.filtered("has_backup_values").ids)
        for vals in vals_list:
            vals["has_backup_values"] = vals.get("plan_log_id") in protected
        return super().create(vals_list)
