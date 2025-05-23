# Copyright 2024 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

"""Constants for the cetmix_tower_aws module."""

from odoo import _

# Boto3 help information for adding to Python command code
BOTO3_HELP_TEXT = _(
    "#  - boto3: Python 'boto3' library for AWS services. "
    "Available methods: 'client', 'resource', 'Session'\n"
    "#    Supports AWS services like EC2, S3, RDS, Lambda, CloudWatch, etc."
)

# HTML-formatted version of boto3 help text for command help display
BOTO3_HELP_TEXT_HTML = _(
    "<ul>"
    "<li><code>boto3</code>: Python 'boto3' library for AWS services. "
    "Available methods: 'client', 'resource', 'Session'<br/>"
    "Supports AWS services like EC2, S3, RDS, Lambda, CloudWatch, etc.<br/>"
    "Please check the <a href='https://boto3.amazonaws.com/v1/documentation/api/latest/index.html' target='_blank'>Boto3 Documentation</a> for the detailed information about the services and methods."  # noqa: E501
    "</li>"
    "</ul>"
)
