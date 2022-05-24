from odoo import fields, models


class CxTowerInterpreter(models.Model):
    _name = "cx.tower.interpreter"
    _description = "Cetmix Tower Interpreter"

    name = fields.Char()
    path = fields.Char()
