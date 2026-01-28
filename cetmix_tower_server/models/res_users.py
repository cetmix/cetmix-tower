from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    cetmix_tower_show_jet_available_states = fields.Boolean(
        help="Show available states in the jet view",
    )

    def _cetmix_tower_access_level(self):
        """
        Returns the access level of the user.

        Returns:
            str: The access level of the user.
            - "1": User
            - "2": Manager
            - "3": Root
        """

        if self.env.user.has_group("cetmix_tower_server.group_root"):
            return "3"
        elif self.env.user.has_group("cetmix_tower_server.group_manager"):
            return "2"
        elif self.env.user.has_group("cetmix_tower_server.group_user"):
            return "1"
        else:
            return False
