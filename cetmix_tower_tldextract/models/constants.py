# Copyright 2025 Cetmix
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Constants for the cetmix_tower_tldextract module."""

from odoo import _

TLD_EXTRACT_HELP_TEXT = _(
    "#  - tldextract: Python 'tldextract' library.\n"
    "#    Parses domain, subdomain and suffix from a domain string.\n"
    "#    Available method: 'extract'"
)

TLD_EXTRACT_HELP_TEXT_HTML = _(
    "<ul>"
    "<li><code>tldextract</code>: Python 'tldextract' library.<br/>"
    "Parses domain, subdomain and suffix from a domain string.<br/>"
    "Available method: <code>extract</code><br/>"
    "See <a href='https://tldextract.readthedocs.io/' "
    "target='_blank'>tldextract docs</a></li>"
    "</ul>"
)
