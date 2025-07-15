# Copyright 2024 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models
from odoo.tools.safe_eval import wrap_module

# Wrap ovh safely
ovh = wrap_module(__import__("ovh"), ["Client"])


class CxTowerCommand(models.Model):
    """Extends cx.tower.command to add OVH functionality."""

    _inherit = "cx.tower.command"

    def _custom_python_libraries(self):
        """
        Add the ovh library to the available libraries.
        """
        python_libraries = super()._custom_python_libraries()
        python_libraries.update(
            {
                "cetmix_tower_ovh": {
                    "ovh": {
                        "import": ovh,
                        "help": _(
                            "Python 'ovh' library for OVH services. "
                            "Available methods: 'Client'<br/>"
                            "Supports OVH services<br/>"
                            "Please check the <a "
                            "href='https://eu.api.ovh.com/console/?section=%2FallDom&branch=v1'"
                            " target='_blank'>OVH Documentation</a> for detailed "
                            "information about the services and methods."
                        ),
                    }
                }
            }
        )
        return python_libraries
