# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerInterpreter(models.Model):
    _name = "cx.tower.interpreter"
    _description = "Cetmix Tower Interpreter"

    name = fields.Char()
    color = fields.Integer(help="For better visualization in views")
    path = fields.Char()
