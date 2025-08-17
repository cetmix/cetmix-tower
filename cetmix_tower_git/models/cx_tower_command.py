# Copyright 2024 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models
from odoo.tools.safe_eval import wrap_module

# Wrap giturlparse safely
giturlparse = wrap_module(__import__("giturlparse"), ["parse", "validate"])


class CxTowerCommand(models.Model):
    """Extends cx.tower.command to add giturlparse functionality."""

    _inherit = "cx.tower.command"

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
