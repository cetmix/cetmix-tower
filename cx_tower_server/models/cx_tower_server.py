# Copyright <YEAR(S)> <AUTHOR(S)>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class OperatingSystem(models.Model):
    _name = "cx.tower.os"
    _description = "Cetmix Tower Operating System"

    name = fields.Char(string="Name", required=True)
    parent_id = fields.Many2one(string="Previous Version", comodel_name="cx.tower.os")


class Tag(models.Model):
    _name = "cx.tower.tag"
    _description = "Cetmix Tower Tag"

    name = fields.Char(string="Name", required=True)
    server_ids = fields.Many2many(string="Servers", comodel_name="cx.tower.server")


class Server(models.Model):
    _name = "cx.tower.server"
    _description = "Cetmix Tower Server"

    active = fields.Boolean(default=True)
    name = fields.Char(string="Name", required=True)
    partner_id = fields.Many2one(string="Partner", comodel_name="res.partner")
    status = fields.Selection(
        string="Status",
        selection=[
            ("starting", "Starting"),
            ("running", "Running"),
            ("stopping", "Stopping"),
            ("stopped", "Stopped"),
        ],
        help="Server status",
    )
    error_code = fields.Char(string="Error Code", help="Latest operation error code")
    ip_v4_address = fields.Char(string="IPv4 Address")
    ip_v6_address = fields.Char(string="IPv6 Address")
    ssh_port = fields.Char(string="SSH port")
    ssh_username = fields.Char(string="SSH Username")
    ssh_password = fields.Char(string="SSH Password")
    ssh_key = fields.Text(string="SSH Private Key")
    ssh_auth_mode = fields.Selection(
        string="SSH Auth Mode",
        selection=[
            ("p", "Password"),
            ("k", "Key"),
        ],
        default="p",
        required=True,
    )
    os_id = fields.Many2one(
        string="Operating System", comodel_name="cx.tower.os", required=True
    )
    tag_ids = fields.Many2many(string="Tags", comodel_name="cx.tower.tag")
    core_count = fields.Integer(string="CPU Core Count", help="Number of CPU cores")
    ram_total = fields.Integer(string="Total RAM, Mb")
    disk_total = fields.Integer(string="Total RAM, Gb")
