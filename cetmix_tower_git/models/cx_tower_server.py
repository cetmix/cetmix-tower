# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class CxTowerServer(models.Model):
    _inherit = "cx.tower.server"

    git_project_rel_ids = fields.One2many(
        comodel_name="cx.tower.git.project.rel",
        inverse_name="server_id",
        copy=False,
        depends=["git_project_ids"],
        groups="cetmix_tower_server.group_manager,cetmix_tower_server.group_root",
    )

    # Helper field to get all git projects related to server
    # IMPORTANT: This field may contain duplicates because of the relation nature!
    git_project_ids = fields.Many2many(
        comodel_name="cx.tower.git.project",
        relation="cx_tower_git_project_rel",
        column1="server_id",
        column2="git_project_id",
        readonly=True,
        copy=False,
        depends=["git_project_rel_ids"],
        groups="cetmix_tower_server.group_manager,cetmix_tower_server.group_root",
    )

    # ------------------------------
    # YAML mixin methods
    # ------------------------------
    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "git_project_rel_ids",
        ]
        return res

    def _get_force_x2m_resolve_models(self):
        res = super()._get_force_x2m_resolve_models()

        # Add File in order to always try to use existing one
        res += ["cx.tower.file"]
        return res

    def _update_or_create_related_record(
        self, model, reference, values, create_immediately=False
    ):
        # Files must be created immediately because they are related
        # to both server and git project.
        # So if a file is not created immediately when it is created
        # for the server, the same file will be created for the git project.
        # This will lead to creation of two files with the same content
        # for the same server.

        if model._name == "cx.tower.file":
            create_immediately = True
        return super()._update_or_create_related_record(
            model, reference, values, create_immediately=create_immediately
        )

    @api.model
    def get_servers_by_git_ref(self, repository_url, head=None, head_type=None):
        """
        Return servers linked to a given Git repository reference.

        Parameters
        ----------
        repository_url : str
            Pre-normalized canonical Git URL
            (e.g. ``https://host/owner/repo.git``).
        head : str, optional
            Branch name, commit SHA, or PR identifier.
        head_type : {'branch', 'commit', 'pr'}, optional
            Type of the ``head`` argument.
            If only ``head`` is provided, it will match across all head types.
            If only ``head_type`` is provided, it will filter by type regardless of head

        Returns
        -------
        recordset of cx.tower.server
            Matching servers. Empty recordset if no matches.
        """
        # URL MUST be already canonical.
        if not repository_url:
            return self.env["cx.tower.server"].browse()

        Remote = self.env["cx.tower.git.remote"]
        domain = [("url", "=", repository_url)]
        if head:
            domain.append(("head", "=", head))
        if head_type:
            domain.append(("head_type", "=", head_type))

        matching = Remote.search(domain)

        servers = matching.mapped("git_project_id.git_project_rel_ids.server_id")
        return servers
