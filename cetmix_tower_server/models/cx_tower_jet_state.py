# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models
from odoo.exceptions import AccessError, ValidationError


class CxTowerJetState(models.Model):
    """Jet States represent the different states a jet can be in during its lifecycle"""

    _name = "cx.tower.jet.state"
    _description = "Cetmix Tower Jet State"
    _inherit = ["cx.tower.reference.mixin", "cx.tower.access.mixin"]
    _order = "sequence, id"

    sequence = fields.Integer(default=10, required=True)
    active = fields.Boolean(default=True)
    color = fields.Integer()
    note = fields.Text()

    # Set default access level to User
    access_level = fields.Selection(default="1")

    def set_state(self, jet=None):
        """Sets the state of the jet

        Args:
            jet (cx.tower.jet): Jet to set the state.
        """
        self.ensure_one()

        # Check if user access level is equal or greater
        # than the state access level
        if self.access_level > self.env.user._cetmix_tower_access_level():
            raise AccessError(
                _("You are not allowed to set the '%(state)s' state!", state=self.name)
            )

        # Try to obtain jet from context if not provided as an argument
        if jet is None:
            jet_id = self.env.context.get("jet_id")

            # Just return, no exceptions for now
            if not jet_id:
                return

            jet = self.env["cx.tower.jet"].browse(jet_id)

        # Ensure that the state is set for a single jet
        if not jet or len(jet) > 1:
            raise ValidationError(_("State can be set only for a single jet"))

        # Bring the jet to the state
        jet._bring_to_state(self)
