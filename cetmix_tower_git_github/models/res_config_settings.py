# Copyright 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """GitHub API secret used when a repository has none of its own."""

    _inherit = "res.config.settings"

    cetmix_tower_git_github_default_secret_id = fields.Many2one(
        comodel_name="cx.tower.key",
        domain="[('key_type', '=', 's')]",
        config_parameter="cetmix_tower_git_github.default_secret_id",
        string="GitHub API Secret",
        help="Secret sent to GitHub when a repository has no Secret of its"
        " own. Applies to a public repository and a private one.",
    )
