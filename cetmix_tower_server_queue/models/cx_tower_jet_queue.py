# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class CxTowerJetQueue(models.Model):
    """Add update NOTIFY mixin to jets when queue_job is installed."""

    _name = "cx.tower.jet"
    _inherit = ["cx.tower.jet", "cx.tower.update.notify.mixin"]
    _description = "Cetmix Tower Jet (queue)"

    NOTIFY_ON_FIELD_UPDATE = ["state"]
