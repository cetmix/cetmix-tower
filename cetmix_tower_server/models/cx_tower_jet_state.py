# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CxTowerJetState(models.Model):
    """Jet States represent the different states a jet can be in during its lifecycle"""

    _name = "cx.tower.jet.state"
    _description = "Cetmix Tower Jet State"
    _inherit = ["cx.tower.reference.mixin"]
    _order = "sequence, id"

    sequence = fields.Integer(default=10, required=True)
    check_dependencies = fields.Boolean(
        help="If enabled, dependencies will be checked "
        "before transitioning to this state"
    )
    active = fields.Boolean(default=True)
    color = fields.Integer()
    note = fields.Text()
