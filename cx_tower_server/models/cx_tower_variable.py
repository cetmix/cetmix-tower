from odoo import fields, models


class TowerVariable(models.Model):
    _name = "cx.tower.variable"
    _description = "Cetmix Tower Variable"

    name = fields.Char(string="Name", required=True)
