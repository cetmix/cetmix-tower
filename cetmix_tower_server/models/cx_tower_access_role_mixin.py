# Copyright (C) 2025 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class CxTowerAccessRoleMixin(models.AbstractModel):
    """Used to implement access roles in models."""

    _name = "cx.tower.access.role.mixin"
    _description = "Cetmix Tower access role mixin"

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

    @api.model_create_multi
    def create(self, vals_list):
        """
        Create records with post-create fields.
        """
        post_create_fields = self._get_post_create_fields()
        post_create_vals_list = []
        for vals in vals_list:
            post_create_vals = {}
            for key in post_create_fields:
                if key in vals:
                    post_create_vals[key] = vals.pop(key)
            post_create_vals_list.append(post_create_vals)

        # Create records without post-create fields
        res = super().create(vals_list)
        if post_create_vals_list:
            # Create related records with post-create field
            for post_create_vals, record in zip(post_create_vals_list, res):  # noqa: B905 we need to run on Python 3.10
                if post_create_vals:
                    record.write(post_create_vals)

        return res

    def _get_post_create_fields(self):
        """
        Get post-create fields.

        Some records may create related records which use rules
        that depend on `user_ids` and `manager_ids` fields.
        However at the moment of record creation, these fields are not yet set.
        So first we create the record without these fields, then we create
        the related records to avoid access violations.

        Returns:
            list: List of fields to be set after record creation.
        """
        return []
