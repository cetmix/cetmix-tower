# Copyright 2024 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Constants for the cetmix_tower_ovh module."""

from odoo import _

# OVH help information for adding to Python command code
OVH_HELP_TEXT = _(
    "#  - ovh: Python 'ovh' library for OVH services. "
    "Available methods: 'Client'\n"
    "#    Supports OVH services\n"
    "#  - tldextract: Python 'tldextract' library. "
    "Available methods: 'extract'\n"
    "#    Supports domain extraction"
)

# HTML-formatted version of OVH help text for command help display
OVH_HELP_TEXT_HTML = _(
    "<ul>"
    "<li><code>ovh</code>: Python 'ovh' library for OVH services.  "
    "Available methods: 'Client'<br/>"
    "Supports OVH services<br/>"
    "Please check the <a href='https://eu.api.ovh.com/console/?section=%2FallDom&branch=v1' target='_blank'>OVH Documentation</a> for the detailed information about the services and methods.</li>"  # noqa: E501
    "<li><code>tldextract</code>: Python 'tldextract' library.  "
    "Available methods: 'extract'<br/>"
    "Supports domain extraction. "
    "See <a href='https://tldextract.readthedocs.io/' "
    "target='_blank'>tldextract docs</a></li>"
    "</ul>"
)
