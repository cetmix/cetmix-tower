# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, fields, models
from odoo.exceptions import ValidationError


class CxTowerTag(models.Model):
    """
    Cetmix Tower Tag.
    Tags are used to group servers, commands, flight plans, etc.
    """

    _name = "cx.tower.tag"
    _inherit = [
        "cx.tower.reference.mixin",
    ]
    _description = "Cetmix Tower Tag"
    _order = "name"

    color = fields.Integer(help="For better visualization in views")

    def unlink(self):
        """
        Prevent deletion of tags that are in use
        unless user is root or using sudo.
        """
        if not self.env.is_superuser() and not self.env.user.has_group(
            "cetmix_tower_base.group_root"
        ):
            self._check_tags_can_be_deleted()
        return super().unlink()

    def _get_tag_usage_fields(self):
        """Relational fields whose non-empty value blocks tag deletion.

        Inheriting modules MUST call super() and extend the list.

        Returns:
            list: field names on cx.tower.tag
        """
        return []

    def _check_tags_can_be_deleted(self):
        """Check if tags can be deleted.

        Raises:
            ValidationError: If tag is in use
        """
        usage_fields = self._get_tag_usage_fields()
        for tag in self:
            if any(tag[field_name] for field_name in usage_fields):
                raise ValidationError(
                    _(
                        "Cannot delete tag '%(tag_name)s' because"
                        " it is used in related records.",
                        tag_name=tag.name,
                    )
                )
