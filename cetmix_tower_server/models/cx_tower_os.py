from odoo import fields, models


class CxTowerOs(models.Model):
    _name = "cx.tower.os"
    _description = "Cetmix Tower Operating System"

    name = fields.Char(required=True)
    color = fields.Integer(help="For better visualization in views")
    parent_id = fields.Many2one(string="Previous Version", comodel_name="cx.tower.os")
