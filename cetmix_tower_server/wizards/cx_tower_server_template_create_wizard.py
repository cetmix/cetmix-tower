# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CxTowerServerTemplateCreateWizard(models.TransientModel):
    """Create new server from template"""

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
    color = fields.Integer(help="For better visualization in views")
    ip_v4_address = fields.Char(string="IPv4 Address")
    ip_v6_address = fields.Char(string="IPv6 Address")
    ssh_port = fields.Char(string="SSH port", default="22")
    ssh_username = fields.Char(
        string="SSH Username",
        required=True,
        help="This is required, however you can change this later "
        "in the server settings",
    )
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
    line_ids = fields.One2many(
        comodel_name="cx.tower.server.template.create.wizard.line",
        inverse_name="wizard_id",
    )

    def _prepare_server_parameters(self):
        """Prepare new server parameters

        Returns:
            dict(): New server parameters
        """
        res = {
            "ip_v4_address": self.ip_v4_address,
            "ip_v6_address": self.ip_v6_address,
            "ssh_port": self.ssh_port,
            "ssh_username": self.ssh_username,
            "ssh_password": self.ssh_password,
            "ssh_key_id": self.ssh_key_id.id,
            "ssh_auth_mode": self.ssh_auth_mode,
        }
        if self.line_ids:
            res.update(
                {
                    "configuration_variables": {
                        line.variable_reference: line.value_char
                        for line in self.line_ids
                    }
                }
            )
        return res

    def action_confirm(self):
        """
        Create and open new created server from template
        """
        self.ensure_one()

        kwargs = self._prepare_server_parameters()
        server = self.server_template_id._create_new_server(self.name, **kwargs)
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_server"
        )
        action.update(
            {"view_mode": "form", "res_id": server.id, "views": [(False, "form")]}
        )
        return action


class CxTowerServerTemplateCreateWizardVariableLine(models.TransientModel):
    """Configuration variables"""

    _name = "cx.tower.server.template.create.wizard.line"
    _description = "Create new server from template variables"

    wizard_id = fields.Many2one("cx.tower.server.template.create.wizard")
    variable_id = fields.Many2one(comodel_name="cx.tower.variable", required=True)
    variable_reference = fields.Char(related="variable_id.reference", readonly=True)
    value_char = fields.Char(string="Value")
