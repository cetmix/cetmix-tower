# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import re

from odoo import _, api, fields, models


class CxTowerGitProject(models.Model):
    """
    Git Project.
    Implements pre-defined git configuration.
    """

    _name = "cx.tower.git.project"
    _description = "Cetmix Tower Git Configuration"

    _inherit = [
        "cx.tower.reference.mixin",
        "cx.tower.yaml.mixin",
    ]

    active = fields.Boolean(default=True)
    # IMPORTANT: This field may contain duplicates because of the relation nature!
    server_ids = fields.Many2many(
        comodel_name="cx.tower.server",
        relation="cx_tower_git_project_rel",
        column1="git_project_id",
        column2="server_id",
        string="Servers",
        readonly=True,
        copy=False,
        help="Servers are added automatically based on the files linked to the project."
        "\nIMPORTANT: This field may contain duplicates"
        " because of the relation nature!",
    )
    source_ids = fields.One2many(
        comodel_name="cx.tower.git.source",
        inverse_name="git_project_id",
        string="Sources",
        auto_join=True,
        copy=True,
    )
    git_project_rel_ids = fields.One2many(
        comodel_name="cx.tower.git.project.rel",
        inverse_name="git_project_id",
        string="Git Project Server File Relations",
        depends=["file_ids"],
        copy=False,
    )
    # Helper field to get all files related to git project
    file_ids = fields.Many2many(
        comodel_name="cx.tower.file",
        relation="cx_tower_git_project_rel",
        column1="git_project_id",
        column2="file_id",
        string="Files",
        readonly=True,
        depends=["git_project_rel_ids"],
        copy=False,
    )

    # -- UI/UX fields
    has_private_remotes = fields.Boolean(
        compute="_compute_has_private_remotes",
        help="Indicates if the project has any private remotes.",
    )
    has_partially_private_remotes = fields.Boolean(
        compute="_compute_has_private_remotes",
        help="Indicates if the project has any partially private remotes.",
    )

    # -- Git Aggregator related fields
    git_aggregator_root_dir = fields.Char(
        help="Git aggregator root directory where sources will be cloned."
        " Eg '/tmp/git-aggregator'"
        " Will use '.' if not set",
    )

    @api.depends(
        "source_ids", "source_ids.remote_ids", "source_ids.remote_ids.is_private"
    )
    def _compute_has_private_remotes(self):
        for project in self:
            project.has_private_remotes = any(
                source.remote_count > 0
                and source.remote_count_private == source.remote_count
                for source in project.source_ids
            )
            project.has_partially_private_remotes = any(
                source.remote_count_private > 0
                and source.remote_count_private != source.remote_count
                for source in project.source_ids
            )

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        # Update related files on create
        res._update_related_files()
        return res

    def write(self, vals):
        res = super().write(vals)
        # Update related files on update
        self._update_related_files()
        return res

    def _update_related_files(self):
        # Update related files on update
        if self.git_project_rel_ids:
            self.git_project_rel_ids._save_to_file()

    def _extract_variables_from_text(self, text):
        """Extract environment variables from text.
        Helper method for file content generation.

        Returns:
            List: List of variables
        """
        variables = re.findall(r"\$([A-Z0-9_]+)", text)
        return list(set(variables))

    # ------------------------------
    # YAML mixin methods
    # ------------------------------
    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "name",
            "source_ids",
            "git_aggregator_root_dir",
        ]
        return res

    # -------------------------------
    # Git Aggregator related methods
    # -------------------------------
    def _git_aggregator_prepare_record(self):
        """Prepare json structure for git aggregator.

        Returns:
            Dict: Json structure for git aggregator
        """
        self.ensure_one()
        values = {}
        for source in self.source_ids:
            if source.enabled and source.remote_count:
                values.update(
                    {
                        f"{self.git_aggregator_root_dir or '.'}/{source.reference}": source._git_aggregator_prepare_record()  # noqa: E501
                    }
                )
        return values

    def _git_aggregator_prepare_yaml_comment(self, yaml_code):
        """Generate commentary for yaml file.
        It includes brief instructions for git aggregator
        and lists environment variables that are required.

        Args:
            yaml_code (str): Yaml code

        Returns:
            Char: comment text or None
        """

        comment_text = _(
            "# This file is generated with Cetmix Tower https://cetmix.com/tower\n"
            "# It's designed to be used with git-aggregator tool developed by Acsone.\n"
            "# Documentation for git-aggregator: https://github.com/acsone/git-aggregator\n"
        )
        variable_list = self._extract_variables_from_text(yaml_code)
        if variable_list:
            comment_text += _(
                "\n# You need to set the following variables in your environment:\n# %(vars)s \n"  # noqa: E501
                "# and run git-aggregator with '--expand-env' parameter.\n",  # noqa: E501
                vars=(", ".join(variable_list)),
            )
        return comment_text
