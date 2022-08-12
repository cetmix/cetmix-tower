from odoo import fields, models


class CxTowerOs(models.Model):
    _name = "cx.tower.os"
    _description = "Cetmix Tower Operating System"

    name = fields.Char(string="Name", required=True)
    parent_id = fields.Many2one(string="Previous Version", comodel_name="cx.tower.os")
