from odoo import fields, models


class CxTowerCommand(models.Model):
    _name = "cx.tower.command"
    _description = "Cetmix Tower Command"

    name = fields.Char()
    interpreter_id = fields.Many2one(
        comodel_name="cx.tower.interpreter",
    )
    server_ids = fields.Many2many(
        comodel_name="cx.tower.server",
        relation="cx_tower_server_command_rel",
        column1="command_id",
        column2="server_id",
        string="Servers",
    )
    os_ids = fields.Many2many(
        comodel_name="cx.tower.os",
        relation="cx_tower_os_command_rel",
        column1="command_id",
        column2="os_id",
        string="OSes",
    )
    code = fields.Text()
