# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CxTowerBackupTemplate(models.Model):
    """Describe the plans and retention policy for a Jet's backups."""

    _name = "cx.tower.backup.template"
    _description = "Cetmix Tower Backup Template"
    _inherit = ["cx.tower.reference.mixin", "cx.tower.yaml.mixin"]
    _order = "sequence, name"

    name = fields.Char(yaml_export=True)
    sequence = fields.Integer(default=10, yaml_export=True)
    jet_template_id = fields.Many2one(
        "cx.tower.jet.template", required=True, ondelete="cascade"
    )
    plan_backup_id = fields.Many2one(
        "cx.tower.plan",
        string="Backup Flight Plan",
        required=True,
        yaml_export="include",
    )
    plan_restore_id = fields.Many2one(
        "cx.tower.plan",
        string="Restore Flight Plan",
        required=True,
        yaml_export="include",
    )
    plan_delete_id = fields.Many2one(
        "cx.tower.plan", string="Delete Flight Plan", yaml_export="include"
    )
    keep_last = fields.Integer(
        default=0,
        yaml_export=True,
        help="Keep this many successful backups per Jet. 0 keeps all.",
    )
    note = fields.Text(yaml_export=True)
    backup_ids = fields.One2many("cx.tower.backup", "backup_template_id", readonly=True)

    _sql_constraints = [
        (
            "keep_last_nonnegative",
            "CHECK(keep_last >= 0)",
            "Keep last cannot be negative.",
        )
    ]

    @api.constrains("plan_backup_id", "plan_restore_id", "plan_delete_id")
    def _check_plans_access_level(self):
        """Reject plans whose execution tree could disclose backup values.

        Returns:
            None: All configured plans and their execution trees are at Root level.

        Raises:
            ValidationError: A configured plan, command or sub-plan is not Root.
        """
        templates = self.sudo()
        plans = (
            templates.plan_backup_id
            | templates.plan_restore_id
            | templates.plan_delete_id
        )
        plans._check_backup_plan_access()

    def write(self, vals):
        """Keep existing backups attached to their original Jet Template.

        Args:
            vals (dict): Fields to update.

        Returns:
            bool: Parent write result.

        Raises:
            AccessError: The caller cannot update these templates.
            ValidationError: A template with backups would change its Jet Template.
        """
        if "jet_template_id" in vals:
            self.check_access("write")
            changed = self.sudo().filtered(
                lambda template: template.jet_template_id.id != vals["jet_template_id"]
            )
            if changed and self.env["cx.tower.backup"].sudo().search_count(
                [("backup_template_id", "in", changed.ids)]
            ):
                raise ValidationError(
                    self.env._(
                        "A Backup Template with backups cannot change its Jet Template."
                    )
                )
        return super().write(vals)
