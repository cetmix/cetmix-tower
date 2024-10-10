# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models
from odoo.exceptions import ValidationError


class CxTowerTag(models.Model):
    _name = "cx.tower.tag"
    _description = "Cetmix Tower Tag"

    name = fields.Char(string="Name", required=True)
    server_ids = fields.Many2many(
        comodel_name="cx.tower.server",
        relation="cx_tower_server_tag_rel",
        column1="tag_id",
        column2="server_id",
        string="Servers",
    )
    color = fields.Integer(help="For better visualization in views")

    def unlink(self):
        for record in self:
            if record.server_ids:
                raise ValidationError(
                    f"Tag {record.name} is used by {record.server_ids}."
                )
        return super().unlink()
