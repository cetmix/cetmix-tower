from odoo import fields, models


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
