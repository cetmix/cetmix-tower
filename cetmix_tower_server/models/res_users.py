from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    USER_ACCESS_LEVEL = "1"
    MANAGER_ACCESS_LEVEL = "2"
    ROOT_ACCESS_LEVEL = "3"

    cetmix_tower_show_jet_available_states = fields.Boolean(
        help="Show available states in the jet view",
    )

    def _cetmix_tower_access_level(self):
        """
        Returns the access level of the current logged-in user
        Not the record user!

        Returns:
            str: The access level of the user.
            - "1": User
            - "2": Manager
            - "3": Root
            False: No access
        """

        if self.env.user.has_group("cetmix_tower_server.group_root"):
            return self.ROOT_ACCESS_LEVEL
        if self.env.user.has_group("cetmix_tower_server.group_manager"):
            return self.MANAGER_ACCESS_LEVEL
        if self.env.user.has_group("cetmix_tower_server.group_user"):
            return self.USER_ACCESS_LEVEL
        return False
