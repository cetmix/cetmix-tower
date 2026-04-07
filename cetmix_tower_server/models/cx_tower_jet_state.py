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

    def unlink(self):
        """
        Do not allow to unlink a state
        if it is used in any action
        """
        actions = self.env["cx.tower.jet.action"].search(
            [
                "|",
                "|",
                ("state_from_id", "in", self.ids),
                ("state_to_id", "in", self.ids),
                ("state_transit_id", "in", self.ids),
            ]
        )
        if actions:
            raise ValidationError(
                _(
                    "Some states are still used in the following actions: %(actions)s"
                    "\nJet templates: %(templates)s",
                    actions=", ".join(set(actions.mapped("name"))),
                    templates=", ".join(set(actions.mapped("jet_template_id.name"))),
                )
            )
        return super().unlink()

    def set_state(self, jet=None):
        """Sets the state of the jet

        Args:
            jet (cx.tower.jet): Jet to set the state.
        """
        self.ensure_one()

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

        # Check access to the jet
        jet.check_access("read")

        # Get user access level
        user_access_level = self.env.user._cetmix_tower_access_level()

        # If user is manager but is not added as a manager to the jet,
        # his access level is considered as user.
        # NB: record access is already checked above.
        if user_access_level == "2" and self.env.user not in jet.manager_ids:
            user_access_level = "1"

        # Check if user access level is equal or greater
        if self.access_level > user_access_level:
            raise AccessError(
                _("You are not allowed to set the '%(state)s' state!", state=self.name)
            )

        # Bring the jet to the state
        jet._bring_to_state(self)
