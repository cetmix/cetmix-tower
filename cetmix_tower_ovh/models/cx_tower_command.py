# Copyright 2024 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models
from odoo.tools.safe_eval import wrap_module

from . import constants

# Wrap ovh safely
ovh = wrap_module(__import__("ovh"), ["Client"])


class CxTowerCommand(models.Model):
    """Extends cx.tower.command to add OVH functionality."""

    _inherit = "cx.tower.command"

    @api.model
    def _get_eval_context(self, server=None):
        """
        Overrides _get_eval_context to add OVH to the evaluation context.
        """
        eval_context = super()._get_eval_context(server=server)
        eval_context.update({"ovh": ovh})
        return eval_context

    def _compute_code(self):
        """Compute default code with OVH information.

        Extends the original method to add OVH documentation
        to Python code commands.
        """
        # First let core populate code
        super()._compute_code()

        for rec in self:
            if rec.action == "python_code" and rec.code:
                formatted_code = rec.code.rstrip()
                # Add OVH client usage examples and documentation
                help_code = f"{formatted_code}\n{constants.OVH_HELP_TEXT}"
                rec.code = help_code

    def _compute_command_help(self):
        """Compute command help with OVH information.

        Extends the original method to add OVH documentation
        to Python code command help.
        """
        # First let core populate command help
        super()._compute_command_help()

        for rec in self:
            if rec.action == "python_code" and rec.command_help:
                help_text = f"{rec.command_help}{constants.OVH_HELP_TEXT_HTML}"
                rec.command_help = help_text
