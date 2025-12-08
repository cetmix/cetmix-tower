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

        server_obj = self.env["cx.tower.server"]
        # URL MUST be already canonical.
        if not repository_url:
            return server_obj

        # Get repository id by URL
        repo_id = self.env["cx.tower.git.repo"]._get_repo_id_by_url(
            repository_url, raise_if_invalid=False
        )
        if not repo_id:
            return server_obj
        repo = self.env["cx.tower.git.repo"].browse(repo_id)

        # Compose domain for remotes
        remote_domain = [
            ("source_id.enabled", "=", True),
            ("enabled", "=", True),
        ]
        if head:
            head = self.env["cx.tower.git.remote"]._sanitize_head(head)
            remote_domain.append(("head", "=", head))
        if head_type:
            remote_domain.append(("head_type", "=", head_type))

        # Get remotes
        remotes = repo.remote_ids.filtered_domain(remote_domain)
        if not remotes:
            return server_obj

        # Get servers from remotes
        servers = remotes.mapped("git_project_id.git_project_rel_ids.server_id")
        return servers

    def _command_runner_file_using_template_create_file(
        self,
        file_template_id,
        server_dir,
        plan_line,
        if_file_exists,
        **kwargs,
    ):
        """Override to create git project relation
        when creating a file using a template.
        """
        file = super()._command_runner_file_using_template_create_file(
            file_template_id, server_dir, plan_line, if_file_exists, **kwargs
        )
        if file and plan_line:
            git_project = plan_line.git_project_id
            if not git_project:
                return file

            if plan_line.is_make_copy:
                # Remove default_server_ids from context, because this relation
                # will be created through git_project_rel_ids.
                # default_server_ids will interfere at the moment when
                # pairs of values are created through SQL query
                # in the method write_real and it does not take into account
                # that in this case we are creating a copy of the git project
                git_project = git_project.with_context(default_server_ids=False).copy()

            self.env["cx.tower.git.project.rel"].create(
                {
                    "git_project_id": git_project.id,
                    "server_id": self.id,
                    "file_id": file.id,
                    "project_format": git_project._default_project_format(),
                }
            )
        return file
