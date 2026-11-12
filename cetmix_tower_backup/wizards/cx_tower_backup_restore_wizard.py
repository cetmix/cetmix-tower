# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class CxTowerBackupRestoreWizard(models.TransientModel):
    _name = "cx.tower.backup.restore.wizard"
    _description = "Restore Backup"

    backup_id = fields.Many2one("cx.tower.backup", required=True, readonly=True)
    server_id = fields.Many2one("cx.tower.server", required=True)
    name = fields.Char()
    state_id = fields.Many2one("cx.tower.jet.state", domain="state_domain")
    state_domain = fields.Binary(compute="_compute_state_domain")
    environment_id = fields.Many2one(
        "cx.tower.environment",
        compute="_compute_environment_id",
        store=True,
        readonly=False,
    )
    env_required = fields.Boolean(related="backup_id.jet_template_id.env_required")

    @api.depends("backup_id")
    def _compute_environment_id(self):
        for wizard in self:
            wizard.environment_id = (
                wizard.backup_id.environment_id
                or wizard.backup_id.jet_template_id.environment_default_id
            )

    @api.depends("backup_id.jet_template_id")
    def _compute_state_domain(self):
        for wizard in self:
            wizard.state_domain = [
                (
                    "id",
                    "in",
                    wizard.backup_id.jet_template_id.action_ids.state_to_id.ids,
                )
            ]

    def action_confirm(self):
        """Restore into a new Jet and open its form.

        Returns:
            dict: New Jet form action.
        """
        self.ensure_one()
        self.check_access("read")
        jet = self.backup_id.restore(
            self.server_id,
            name=self.name,
            state=self.state_id,
            environment=self.environment_id,
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "cx.tower.jet",
            "res_id": jet.id,
            "view_mode": "form",
            "target": "current",
        }
