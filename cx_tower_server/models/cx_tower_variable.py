from odoo import _, api, fields, models


class TowerVariable(models.Model):
    _name = "cx.tower.variable"
    _description = "Cetmix Tower Variable"
    _order = "name"

    name = fields.Char(string="Name", required=True)
