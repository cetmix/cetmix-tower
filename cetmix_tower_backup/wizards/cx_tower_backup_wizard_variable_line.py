# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class CxTowerBackupCreateWizardVariableLine(models.TransientModel):
    _name = "cx.tower.backup.create.wizard.variable.line"
    _inherit = "cx.tower.custom.variable.value.mixin"
    _description = "Backup Create Custom Value"

    wizard_id = fields.Many2one(
        "cx.tower.backup.create.wizard", required=True, ondelete="cascade"
    )
    variable_id = fields.Many2one(required=True)

    @api.constrains("wizard_id")
    def _check_wizard_access(self):
        """Prevent attaching a value to another user's protected dialog.

        Returns:
            None: Every referenced wizard is writable by the caller.

        Raises:
            AccessError: A referenced wizard belongs to another user.
        """
        self.wizard_id.check_access("write")


class CxTowerBackupRestoreWizardVariableLine(models.TransientModel):
    _name = "cx.tower.backup.restore.wizard.variable.line"
    _inherit = "cx.tower.custom.variable.value.mixin"
    _description = "Backup Restore Custom Value"

    wizard_id = fields.Many2one(
        "cx.tower.backup.restore.wizard", required=True, ondelete="cascade"
    )
    variable_id = fields.Many2one(required=True)

    @api.constrains("wizard_id")
    def _check_wizard_access(self):
        """Prevent attaching a value to another user's protected dialog.

        Returns:
            None: Every referenced wizard is writable by the caller.

        Raises:
            AccessError: A referenced wizard belongs to another user.
        """
        self.wizard_id.check_access("write")
