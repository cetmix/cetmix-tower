# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CxTowerServerTemplateCreateWizard(models.TransientModel):
    _name = "cx.tower.server.template.create.wizard"
    _description = "Create new server from template"

    server_template_id = fields.Many2one(
        "cx.tower.server.template",
        string="Server Template",
        readonly=True,
    )
    name = fields.Char(
        string="Server Name",
        required=True,
    )
    ip_v4_address = fields.Char(string="IPv4 Address")
    ip_v6_address = fields.Char(string="IPv6 Address")
    ssh_port = fields.Char(string="SSH port", required=True, default="22")
    ssh_username = fields.Char(string="SSH Username", required=True)
    ssh_password = fields.Char(string="SSH Password")
    ssh_key_id = fields.Many2one(
        comodel_name="cx.tower.key",
        string="SSH Private Key",
        domain=[("key_type", "=", "k")],
    )
    ssh_auth_mode = fields.Selection(
        string="SSH Auth Mode",
        selection=[
            ("p", "Password"),
            ("k", "Key"),
        ],
        default="p",
        required=True,
    )

    def action_confirm(self):
        """
        Create and open new created server from template
        """
        self.ensure_one()
        server = self.server_template_id._create_new_server(
            self.name,
            ip_v4_address=self.ip_v4_address,
            ip_v6_address=self.ip_v6_address,
            ssh_port=self.ssh_port,
            ssh_username=self.ssh_username,
            ssh_password=self.ssh_password,
            ssh_key_id=self.ssh_key_id.id,
            ssh_auth_mode=self.ssh_auth_mode,
        )
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_server"
        )
        action.update(
            {"view_mode": "form", "res_id": server.id, "views": [(False, "form")]}
        )
        return action
