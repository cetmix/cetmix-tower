# Copyright 2024 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models
from odoo.tools.safe_eval import wrap_module

boto3 = wrap_module(__import__("boto3"), ["client", "Session"])


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
        """
        Compute default code, extending the original method
        to include boto3 information.
        """
        super(CxTowerCommand, self)._compute_code()  # Call the original method first

        boto3_line = (
            "#  - boto3: Python 'boto3' library. Available methods: 'client', 'Session'"
        )

        for command in self:
            if command.action == "python_code" and command.code:
                lines = command.code.split("\n")
                # Find the appropriate place to insert the boto3 line.
                insert_index = 0
                for i, line in enumerate(lines):
                    if line.startswith("#  -"):
                        insert_index = i + 1
                lines.insert(insert_index, boto3_line)
                command.code = "\n".join(lines)
