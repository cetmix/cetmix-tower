# Copyright 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CxTowerGitGithubSyncWizard(models.TransientModel):
    """Confirm overwriting a stored GitHub owner id."""

    _name = "cx.tower.git.github.sync.wizard"
    _description = "Confirm GitHub owner id overwrite"

    line_ids = fields.One2many(
        comodel_name="cx.tower.git.github.sync.wizard.line",
        inverse_name="wizard_id",
    )

    def action_overwrite(self):
        """Store the GitHub owner ids fetched from GitHub.

        Raises:
            AccessError: The current user cannot write an owner.

        Returns:
            dict: Action that closes the wizard.
        """
        self.ensure_one()
        for line in self.line_ids:
            line.owner_id.write({"github_owner_ref": line.fetched_github_owner_ref})
        return {"type": "ir.actions.act_window_close"}

    def action_cancel(self):
        """Leave stored owner ids unchanged.

        Returns:
            dict: Action that closes the wizard.
        """
        self.ensure_one()
        return {"type": "ir.actions.act_window_close"}


class CxTowerGitGithubSyncWizardLine(models.TransientModel):
    """One owner whose stored GitHub id differs from GitHub."""

    _name = "cx.tower.git.github.sync.wizard.line"
    _description = "GitHub owner id confirmation line"

    wizard_id = fields.Many2one(
        comodel_name="cx.tower.git.github.sync.wizard",
        required=True,
        ondelete="cascade",
    )
    owner_id = fields.Many2one(
        comodel_name="cx.tower.git.repo.owner",
        required=True,
        readonly=True,
    )
    stored_github_owner_ref = fields.Char(readonly=True)
    fetched_github_owner_ref = fields.Char(readonly=True)
