from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    cetmix_tower_show_jet_available_states = fields.Boolean(
        help="Show available states in the jet view",
    )
