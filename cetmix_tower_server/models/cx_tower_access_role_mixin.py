# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerAccessRoleMixin(models.AbstractModel):
    """Used to implement access roles in models."""

    _name = "cx.tower.access.role.mixin"
    _description = "Cetmix Tower access role mixin"

    def _default_user_ids(self):
        """
        Default Users for new Records.
        """
        # If user is in group_user, add them to the list
        if self.env.user.has_group("cetmix_tower_server.group_user"):
            return [self.env.user.id]
        # Otherwise, return an empty list. Eg if created using sudo()
        return []

    def _default_manager_ids(self):
        """
        Default Managers for new Records.
        """
        # If user is manager, add them to the list
        if self.env.user.has_group("cetmix_tower_server.group_manager"):
            return [self.env.user.id]
        # Otherwise, return an empty list. Eg if created using sudo()
        return []

    # IMPORTANT: inherit these fields in your model
    #  add 'relation' key explicitly to the field.
    # Use 'cx.tower.server' as model as a reference.
    user_ids = fields.Many2many(
        comodel_name="res.users",
        column1="record_id",
        column2="user_id",
        string="Users",
        domain=lambda self: [
            ("groups_id", "in", [self.env.ref("cetmix_tower_server.group_user").id])
        ],
        default=lambda self: self._default_user_ids(),
        help="Users who can view this record",
        copy=False,
    )

    manager_ids = fields.Many2many(
        comodel_name="res.users",
        column1="record_id",
        column2="manager_id",
        string="Managers",
        groups="cetmix_tower_server.group_manager",
        domain=lambda self: [
            ("groups_id", "in", [self.env.ref("cetmix_tower_server.group_manager").id])
        ],
        default=lambda self: self._default_manager_ids(),
        help="Managers who can modify this record",
        copy=False,
    )
