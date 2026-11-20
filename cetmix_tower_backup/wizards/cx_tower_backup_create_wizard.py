# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerBackupCreateWizard(models.TransientModel):
    _name = "cx.tower.backup.create.wizard"
    _description = "Back Up Jet"

    jet_id = fields.Many2one("cx.tower.jet", required=True, readonly=True)
    name = fields.Char(help="Leave blank to generate a backup name.")
    jet_template_id = fields.Many2one(related="jet_id.jet_template_id")
    backup_template_id = fields.Many2one(
        "cx.tower.backup.template",
        required=True,
        domain="[('jet_template_id', '=', jet_template_id)]",
    )

    available_variable_ids = fields.Many2many(
        related="backup_template_id.backup_available_variable_ids"
    )
    line_ids = fields.One2many(
        "cx.tower.backup.create.wizard.variable.line",
        "wizard_id",
        string="Custom Values",
    )

    def action_confirm(self):
        """Start the selected backup and open its record.

        Returns:
            dict: Backup form action.

        Raises:
            ValidationError: Custom values are not permitted by the template.
        """
        self.ensure_one()
        self.check_access("read")
        backup = self.jet_id.create_backup(
            self.backup_template_id,
            name=self.name,
            variable_values=self.backup_template_id._get_wizard_variable_values(
                self.line_ids, "backup"
            ),
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "cx.tower.backup",
            "res_id": backup.id,
            "view_mode": "form",
            "target": "current",
        }
