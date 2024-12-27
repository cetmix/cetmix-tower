# Copyright 2024 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models
from odoo.tools.safe_eval import wrap_module

from . import constants

# Wrap boto3 safely
boto3 = wrap_module(__import__("boto3"), ["client", "resource", "Session"])


class CxTowerCommand(models.Model):
    """Extends cx.tower.command to add AWS boto3 functionality."""

    _inherit = "cx.tower.command"

    @api.model
    def _get_eval_context(self, server=None):
        """
        Overrides _get_eval_context to add boto3 to the evaluation context.
        """
        eval_context = super()._get_eval_context(server=server)
        eval_context["boto3"] = boto3
        return eval_context

    def _compute_code(self):
        """Compute default code with boto3 information.

        Extends the original method to add boto3 documentation
        to Python code commands.
        """
        # First let core populate code
        super()._compute_code()

        for rec in self:
            if rec.action == "python_code" and rec.code:
                formatted_code = rec.code.rstrip() + "\n"
                # Append the boto3 help text
                rec.code = formatted_code + constants.BOTO3_HELP_TEXT

    def _compute_command_help(self):
        """Compute command help with boto3 information.

        Extends the original method to add boto3 documentation
        to Python code command help.
        """
        # First let core populate command help
        super()._compute_command_help()

        for rec in self:
            if rec.action == "python_code" and rec.command_help:
                # This ensures our boto3 help is added as a list item within
                # the existing list of available variables, regardless of future
                # changes to the upstream template structure
                if "</ul>" in rec.command_help:
                    # Insert boto3 help as a list item before the closing </ul> tag
                    help_text = rec.command_help.replace(
                        "</ul>", constants.BOTO3_HELP_TEXT_HTML + "</ul>"
                    )
                else:
                    # Fallback: if structure changes and </ul> isn't found,
                    # append to the end with proper HTML formatting
                    help_text = (
                        f"{rec.command_help}<br/>{constants.BOTO3_HELP_TEXT_HTML}"
                    )

                rec.command_help = help_text
