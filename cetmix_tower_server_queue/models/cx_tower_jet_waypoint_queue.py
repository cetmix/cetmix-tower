# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class CxTowerJetWaypointQueue(models.Model):
    """Add update NOTIFY mixin to waypoints when queue_job is installed."""

    _name = "cx.tower.jet.waypoint"
    _inherit = ["cx.tower.jet.waypoint", "cx.tower.update.notify.mixin"]
    _description = "Cetmix Tower Jet Waypoint (queue)"

    NOTIFY_ON_FIELD_UPDATE = ["state"]
