# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerTag(models.Model):
    """Cetmix Tower Tag — server-side relations."""

    _inherit = "cx.tower.tag"

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

    def _get_tag_usage_fields(self):
        """Extend the deletion check with server-side relations.

        Returns:
            list: field names on cx.tower.tag
        """
        return super()._get_tag_usage_fields() + [
            "server_ids",
            "command_ids",
            "plan_ids",
            "server_template_ids",
            "file_template_ids",
        ]
