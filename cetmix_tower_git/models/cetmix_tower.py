# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models


class CetmixTower(models.AbstractModel):
    _inherit = "cetmix.tower"

    @api.model
    def servers_by_git_ref(self, repository_url, head=None, head_type=None):
        """
        Return servers linked to a given Git repository reference.

        This is a thin shortcut that delegates to
        :meth:`cx.tower.server.get_servers_by_git_ref`.

        Parameters
        ----------
        repository_url : str
            Pre-normalized canonical Git URL
            (e.g. ``https://host/owner/repo.git``).
        head : str, optional
            Branch name, commit SHA, or PR identifier.
        head_type : {'branch', 'commit', 'pr'}, optional
            Type of the ``head`` argument.

        Returns
        -------
        recordset of cx.tower.server
            Matching servers. Empty recordset if no matches.
        """
        return self.env["cx.tower.server"].get_servers_by_git_ref(
            repository_url, head, head_type
        )
