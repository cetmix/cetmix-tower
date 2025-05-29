# Copyright 2025 Cetmix
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tools.safe_eval import wrap_module

tldextract = wrap_module(__import__("tldextract"), ["extract"])
