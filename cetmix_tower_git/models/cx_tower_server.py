# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


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
