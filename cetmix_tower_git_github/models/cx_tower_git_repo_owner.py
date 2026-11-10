# Copyright 2026 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CxTowerGitRepoOwner(models.Model):
    """GitHub account id for a repository owner on github.com."""

    _inherit = "cx.tower.git.repo.owner"

    github_owner_ref = fields.Char(
        help="GitHub owner id returned by GitHub. Not shown in the UI.",
    )
    secret_id = fields.Many2one(
        comodel_name="cx.tower.key",
        help="Secret sent when listing branches, pull requests, and"
        " commits for repositories of this owner, and when reading the"
        " GitHub repository id. Used when the repository Secret is empty."
        " When this is also empty, Tower uses the GitHub API Secret from"
        " General Settings. Reading the GitHub id uses only a global value"
        " of the chosen secret. A value set for a server or a partner is"
        " not used for that read. Head autocomplete still uses the server"
        " and partner when they are known. Private HTTPS clone URLs still"
        " use $GITHUB_TOKEN.",
    )
