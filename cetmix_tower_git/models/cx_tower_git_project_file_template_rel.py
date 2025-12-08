# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CxTowerGitProjectFileTemplateRel(models.Model):
    """
    Relation between git projects and file templates.
    """

    _name = "cx.tower.git.project.file.template.rel"
    _table = "cx_tower_git_project_file_template_rel"
    _description = "Cetmix Tower Git Project relation to File Templates"
    _log_access = False

    name = fields.Char(related="git_project_id.name", readonly=True)
    git_project_id = fields.Many2one(
        comodel_name="cx.tower.git.project",
        index=True,
        required=True,
        ondelete="cascade",
    )
    file_template_id = fields.Many2one(
        comodel_name="cx.tower.file.template",
        required=True,
        ondelete="cascade",
    )
    project_format = fields.Selection(
        selection=lambda self: self.env[
            "cx.tower.git.project"
        ]._selection_project_format(),
        default=lambda self: self.env["cx.tower.git.project"]._default_project_format(),
        required=True,
        string="Format",
    )

    _sql_constraints = [
        (
            "project_server_file_template_format_uniq",
            "unique(git_project_id, file_template_id, project_format)",
            "File template is already related to the same project and format",
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)

        # Export project to file
        res._save_to_file_template()
        return res

    def write(self, vals):
        res = super().write(vals)
        # Export project to file
        self._save_to_file_template()
        return res

    def action_open_file_template(self):
        """
        Open file template record in current window
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.file_template_id.name,
            "res_model": "cx.tower.file.template",
            "res_id": self.file_template_id.id,  # pylint: disable=no-member
            "view_mode": "form",
            "view_type": "form",
            "target": "current",
        }

    # ----------------------------------------------------
    # Save project to linked file based on selected format
    # ----------------------------------------------------
    def _save_to_file_template(self):
        """Save project to linked file using format-specific function."""

        # Get required function based on project format
        # Following the pattern: _generate_code__<format> where format
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
                    record.git_project_id,
                    f"_generate_code_{record.project_format}",
                    None,
                )
                if not code_generator_function:
                    raise ValidationError(
                        _(
                            "Code generator function for '%(project_format)s'"
                            " format not found.",
                            project_format=record.project_format,
                        )
                    )
                code_generator_functions[record.project_format] = (
                    code_generator_function
                )

            # Generate code for current record
            code = code_generator_function(record)
            if record.file_template_id.code != code:
                record.file_template_id.write({"code": code})
