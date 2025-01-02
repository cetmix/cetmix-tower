# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CxTowerGitProjectRel(models.Model):
    """
    Relation between git projects and other model records.
    """

    _name = "cx.tower.git.project.rel"
    _table = "cx_tower_git_project_rel"
    _description = "Git Project relation to other model records"
    _log_access = False

    name = fields.Char(related="git_project_id.name", readonly=True)
    git_project_id = fields.Many2one(
        comodel_name="cx.tower.git.project",
        index=True,
        required=True,
        ondelete="cascade",
    )
    server_id = fields.Many2one(
        comodel_name="cx.tower.server",
        index=True,
        required=True,
        ondelete="cascade",
    )
    file_id = fields.Many2one(
        comodel_name="cx.tower.file",
        domain="[('server_id', '=', server_id),"
        "('source', '=', 'tower'),"
        "('file_type', '=', 'text')]",
        required=True,
        ondelete="cascade",
    )
    project_format = fields.Selection(
        selection=lambda self: self._selection_project_format(),
        required=True,
        string="Format",
    )

    _sql_constraints = [
        (
            "project_server_file_format_uniq",
            "unique(git_project_id, file_id, project_format)",
            "File is already related to the same project and format",
        ),
    ]

    @api.constrains("server_id", "file_id")
    def _check_server_file_relation(self):
        """
        Check if server and file are related.
        """
        for record in self:
            if record.server_id != record.file_id.server_id:
                raise ValidationError(
                    _(
                        "File '%(file)s' doesn't belong to server '%(server)s'",
                        file=record.file_id.name,
                        server=record.server_id.name,
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)

        # Export project to file
        res._save_to_file()
        return res

    def write(self, vals):
        res = super().write(vals)
        # Export project to file
        self._save_to_file()
        return res

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

    # ----------------------------------------------------
    # Save project to linked file based on selected format
    # ----------------------------------------------------
    def _save_to_file(self):
        """Save project to linked file using format-specific function."""

        # Get required function based on project format
        # Following the pattern: _save_to_file_<format> where format
        # is one of the values in _selection_project_format
        # Function gets a single record as an argument.

        # Save resolved functions to dict for faster access
        code_generator_functions = {}

        for record in self:
            code_generator_function = code_generator_functions.get(
                record.project_format
            )
            if not code_generator_function:
                code_generator_function = getattr(
                    self, f"_generate_code_{record.project_format}", None
                )
                if not code_generator_function:
                    raise ValidationError(
                        _(
                            "Code generator function for '%(project_format)s'"
                            " format not found.",
                            project_format=record.project_format,
                        )
                    )
                code_generator_functions[
                    record.project_format
                ] = code_generator_function

            # Generate code for current record
            code = code_generator_function(record)
            if record.file_id.code != code:
                record.file_id.write({"code": code})

    def _generate_code_git_aggregator(self, record):
        """Generate code in git-aggregator format.

        Args:
            record (cx.tower.git.project.rel()): Model record to generate code for.
                must be a single record.

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
