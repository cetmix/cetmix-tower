# Copyright (C) 2026 Crumges
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CxTowerJet(models.Model):
    _inherit = "cx.tower.jet"

    exclude_from_sync = fields.Boolean(
        string="Exclude from Sync",
        default=False,
        help="If checked, this jet will not be affected by template synchronization.",
    )
