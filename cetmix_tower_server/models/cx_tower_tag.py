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

    # --- Relations
    server_ids = fields.Many2many(
        comodel_name="cx.tower.server",
        relation="cx_tower_server_tag_rel",
        column1="tag_id",
        column2="server_id",
        string="Servers",
    )
    command_ids = fields.Many2many(
        comodel_name="cx.tower.command",
        relation="cx_tower_command_tag_rel",
        column1="tag_id",
        column2="command_id",
        string="Commands",
    )
    plan_ids = fields.Many2many(
        comodel_name="cx.tower.plan",
        relation="cx_tower_plan_tag_rel",
        column1="tag_id",
        column2="plan_id",
        string="Plans",
    )
    server_template_ids = fields.Many2many(
        comodel_name="cx.tower.server.template",
        relation="cx_tower_server_template_tag_rel",
        column1="tag_id",
        column2="server_template_id",
        string="Server Templates",
    )
    file_template_ids = fields.Many2many(
        comodel_name="cx.tower.file.template",
        relation="cx_tower_file_template_tag_rel",
        column1="tag_id",
        column2="file_template_id",
        string="File Templates",
    )

    def unlink(self):
        """
        Prevent deletion of tags that are in use
        unless user is root or using sudo.
        """
        if not self.env.is_superuser() and not self.env.user.has_group(
            "cetmix_tower_server.group_root"
        ):
            self._check_tags_can_be_deleted()
        return super().unlink()

    def _check_tags_can_be_deleted(self):
        """Check if tags can be deleted.

        Raises:
            ValidationError: If tag is in use
        """

        for tag in self:
            if (
                tag.server_ids
                or tag.command_ids
                or tag.plan_ids
                or tag.server_template_ids
                or tag.file_template_ids
            ):
                raise ValidationError(
                    _(
                        "Cannot delete tag '%(tag_name)s' because"
                        " it is used in related records.",
                        tag_name=tag.name,
                    )
                )
