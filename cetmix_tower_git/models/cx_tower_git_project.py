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
    _description = "Cetmix Tower Git Project"
    _order = "name"

    _inherit = [
        "cx.tower.reference.mixin",
        "cx.tower.yaml.mixin",
        "cx.tower.access.role.mixin",
    ]

    def _get_post_create_fields(self):
        res = super()._get_post_create_fields()
        return res + [
            "source_ids",
            "git_project_rel_ids",
            "git_project_file_template_rel_ids",
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
    git_project_file_template_rel_ids = fields.One2many(
        comodel_name="cx.tower.git.project.file.template.rel",
        inverse_name="git_project_id",
        string="Git Project File Template Relations",
        copy=False,
    )
    # Helper field to get all file templates related to git project
    file_template_ids = fields.Many2many(
        comodel_name="cx.tower.file.template",
        relation="cx_tower_git_project_file_template_rel",
        column1="git_project_id",
        column2="file_template_id",
        string="File Templates",
        readonly=True,
        depends=["git_project_file_template_rel_ids"],
        copy=False,
    )
    # Helper field to get all repositories used in this project
    repo_ids = fields.Many2many(
        comodel_name="cx.tower.git.repo",
        relation="cx_tower_git_repo_project_rel",
        column1="project_id",
        column2="repo_id",
        string="Repositories",
        readonly=True,
        copy=False,
        help="Repositories used in this project through its sources and remotes",
    )
    note = fields.Text()

    # ---- Access. Add relation for mixin fields
    user_ids = fields.Many2many(
        relation="cx_tower_git_project_user_rel",
        compute="_compute_user_ids",
        readonly=False,
        store=True,
        precompute=True,
    )
    manager_ids = fields.Many2many(
        relation="cx_tower_git_project_manager_rel",
        compute="_compute_user_ids",
        readonly=False,
        store=True,
        precompute=True,
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

    def _selection_project_format(self):
        """
        Possible project formats.
        Inherit and extend when adding new project formats.

        Returns:
            List of tuples: (code, name)
        """
        return [
            ("git_aggregator", "Git Aggregator"),
        ]

    def _default_project_format(self):
        """
        Default project format.
        """
        return "git_aggregator"

    @api.depends(
        "git_project_rel_ids.server_id",
        "git_project_rel_ids.server_id.user_ids",
        "git_project_rel_ids.server_id.manager_ids",
    )
    def _compute_user_ids(self):
        """
        Users. All users who have "Manager" group and are either set in "Users"
        or in "Managers" in all related servers.
        Managers. All users who have "Manager" group and are set as "Managers"
        in all related servers.

        This is done to avoid unpredictable consequences when some of the servers
        are not updated due to access restrictions when a project is updated.
        """
        for project in self:
            # Do not compute if no servers are related
            server_ids = project.git_project_rel_ids.server_id
            if not server_ids:
                continue

            # Get all user and manager ids from related servers
            all_user_ids = server_ids.user_ids.filtered(
                lambda u: u.has_group("cetmix_tower_server.group_manager")
            ).ids
            all_manager_ids = server_ids.manager_ids.ids

            # Create a final list of user and manager ids
            user_ids = []
            manager_ids = []
            # Check if user is present in all servers
            for user_id in all_user_ids:
                if all(
                    user_id in server.user_ids.ids or user_id in server.manager_ids.ids
                    for server in server_ids
                ):
                    user_ids.append(user_id)
            # Check if manager is present in all servers
            for manager_id in all_manager_ids:
                if all(manager_id in server.manager_ids.ids for server in server_ids):
                    manager_ids.append(manager_id)

            # Set the final lists
            project.update(
                {
                    "user_ids": [(6, 0, user_ids)],
                    "manager_ids": [(6, 0, manager_ids)],
                }
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
        # Update related files and templates on create
        res._update_related_files_and_templates()
        return res

    def write(self, vals):
        res = super().write(vals)
        # Update related files and templates on update
        self._update_related_files_and_templates()
        return res

    def _update_related_files_and_templates(self):
        # Update related files and templates
        if self.git_project_rel_ids:
            self.git_project_rel_ids._save_to_file()
        if self.git_project_file_template_rel_ids:
            self.git_project_file_template_rel_ids._save_to_file_template()

    def _extract_variables_from_text(self, text):
        """Extract environment variables from text.
        Helper method for file content generation.

        Returns:
            List: List of variables
        """
        # This regex will find all variables where variables are denoted
        # as $VAR or ${VAR}, e.g., $FOO or ${FOO_BAR123}
        variables = re.findall(r"\$\{?([A-Z0-9_]+)\}?", text)
        return sorted(list(set(variables)))

    # ------------------------------
    # YAML mixin methods
    # ------------------------------
    def _get_fields_for_yaml(self):
        res = super()._get_fields_for_yaml()
        res += [
            "name",
            "note",
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
                root_dir = self.git_aggregator_root_dir or "."
                values.update(
                    {
                        f"/{source.reference}"
                        if root_dir == "/"
                        else f"{root_dir}/{source.reference}": source._git_aggregator_prepare_record()  # noqa: E501
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
                "\n# You need to set the following variables in your environment:\n# %(vars)s\n"  # noqa: E501
                "# and run git-aggregator with '--expand-env' parameter.\n",  # noqa: E501
                vars=(", ".join(variable_list)),
            )
        return comment_text

    def _generate_code_git_aggregator(self, record):
        """Generate code in git-aggregator format.

        Args:
            record (recordset()): Model record to generate code for.
                must be a single record and have git_project_id field.

        Returns:
            Text: Yaml code
        """
        yaml_mixin = self.env["cx.tower.yaml.mixin"]

        # Do not generate code if record values are empty
        record_values = record.git_project_id._git_aggregator_prepare_record()
        if record_values:
            yaml_code = yaml_mixin._convert_dict_to_yaml(record_values)
            # Prepend comment to yaml code
            comment = record.git_project_id._git_aggregator_prepare_yaml_comment(
                yaml_code
            )
            return f"{comment}\n{yaml_code}"
        return ""
