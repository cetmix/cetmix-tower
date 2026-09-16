# Copyright 2024 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, fields, models
from odoo.tools.safe_eval import wrap_module

# Wrap giturlparse safely
giturlparse = wrap_module(__import__("giturlparse"), ["parse", "validate"])


class CxTowerCommand(models.Model):
    """Extends cx.tower.command to add giturlparse functionality."""

    _inherit = "cx.tower.command"

    git_file_name = fields.Char(
        string="File Name",
        help="File name without path. Variables are allowed.",
    )

    @classmethod
    def _get_depends_fields(cls):
        """Include ``git_file_name`` in command hash dependencies.

        Returns:
            list: Field names the command depends on.
        """
        return super()._get_depends_fields() + ["git_file_name"]

    def _selection_action(self):
        """Add the Upload Git Project command action.

        Returns:
            list: Action selection pairs.
        """
        res = super()._selection_action()
        return res + [("git_project_upload", "Upload Git Project")]

    def _get_fields_for_yaml(self):
        """Export ``git_file_name`` with the command YAML.

        Returns:
            list: YAML field names.
        """
        res = super()._get_fields_for_yaml()
        res += [
            "git_file_name",
        ]
        return res

    def _custom_python_libraries(self):
        """
        Add the giturlparse library to the available libraries.
        """
        custom_python_libraries = super()._custom_python_libraries()
        custom_python_libraries.update(
            {
                "cetmix_tower_git": {
                    "giturlparse": {
                        "import": giturlparse,
                        "help": _(
                            "Python library for Git URL parsing. "
                            "Available methods: 'parse', 'validate'. "
                            " <a "
                            "href='https://github.com/nephila/giturlparse/'"
                            " target='_blank'>Documentation on GitHub</a>."
                        ),
                    },
                }
            }
        )
        return custom_python_libraries
