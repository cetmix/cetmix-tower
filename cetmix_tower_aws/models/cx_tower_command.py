# Copyright 2024 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, models
from odoo.tools.safe_eval import wrap_module

# Wrap boto3 safely
boto3 = wrap_module(__import__("boto3"), ["client", "resource", "Session"])


class CxTowerCommand(models.Model):
    """Extends cx.tower.command to add AWS boto3 functionality."""

    _inherit = "cx.tower.command"

    def _custom_python_libraries(self):
        """
        Add the boto3 library to the available libraries.
        """
        custom_python_libraries = super()._custom_python_libraries()
        custom_python_libraries.update(
            {
                "cetmix_tower_aws": {
                    "boto3": {
                        "import": boto3,
                        "help": _(
                            "Python 'boto3' library for AWS services. "
                            "Available methods: 'client', 'resource', 'Session'<br/>"
                            "Supports AWS services like EC2, S3, RDS, Lambda, "
                            "CloudWatch, etc.<br/>"
                            "Please check the <a "
                            "href='https://boto3.amazonaws.com/v1/documentation/api/latest/index.html'"
                            " target='_blank'>Boto3 Documentation</a> for the detailed "
                            "information about the services and methods."
                        ),
                    },
                }
            }
        )
        return custom_python_libraries
