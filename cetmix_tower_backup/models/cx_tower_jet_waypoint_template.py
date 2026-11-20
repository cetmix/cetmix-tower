# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CxTowerJetWaypointTemplate(models.Model):
    _inherit = "cx.tower.jet.waypoint.template"

    backup_template_id = fields.Many2one(
        "cx.tower.backup.template",
        ondelete="restrict",
        groups="cetmix_tower_base.group_root",
        yaml_export="reference",
    )

    @api.constrains(
        "backup_template_id",
        "plan_create_id",
        "plan_delete_id",
        "jet_template_id",
        "plan_arrive_id",
        "plan_leave_id",
    )
    def _check_backup_template(self):
        """Keep backup ownership and waypoint flight plans consistent.

        Returns:
            None: All configured backup waypoint templates are valid.

        Raises:
            ValidationError: A template mixes backup and Create/Delete plans,
                belongs to a different Jet Template, or uses non-Root plans.
        """
        for template in self.sudo():
            if not template.backup_template_id:
                continue
            if template.plan_create_id or template.plan_delete_id:
                raise ValidationError(
                    self.env._(
                        "A backup waypoint cannot have separate Create or "
                        "Delete flight plans."
                    )
                )
            if template.backup_template_id.jet_template_id != template.jet_template_id:
                raise ValidationError(
                    self.env._(
                        "The Backup Template must belong to the same Jet Template."
                    )
                )
            (
                template.plan_arrive_id | template.plan_leave_id
            )._check_backup_plan_access()
