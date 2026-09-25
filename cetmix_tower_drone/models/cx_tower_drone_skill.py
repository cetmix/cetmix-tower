# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class CxTowerDroneSkill(models.Model):
    """Kind of work a drone controller has reported.

    Records are created from a health reply. This module ships none.
    """

    _name = "cx.tower.drone.skill"
    _inherit = [
        "cx.tower.reference.mixin",
    ]
    _description = "Cetmix Tower Drone Skill"
    _order = "name"
