# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class CxTowerServerTemplate(models.Model):
    """Server Template. Used to simplify server creation"""

    _name = "cx.tower.server.template"
    _inherit = ["cx.tower.variable.mixin", "mail.thread", "mail.activity.mixin"]
    _description = "Cetmix Tower Server Template"

    active = fields.Boolean(default=True)
    name = fields.Char(required=True)

    # -- Connection
    ssh_username = fields.Char(string="SSH Username")
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
    )
    use_sudo = fields.Selection(
        string="Use sudo",
        selection=[("n", "Without password"), ("p", "With password")],
        help="Run commands using 'sudo'",
    )

    # ---- Attributes
    color = fields.Integer(help="For better visualization in views")
    os_id = fields.Many2one(string="Operating System", comodel_name="cx.tower.os")
    tag_ids = fields.Many2many(
        comodel_name="cx.tower.tag",
        relation="cx_tower_server_template_tag_rel",
        column1="server_template_id",
        column2="tag_id",
        string="Tags",
    )

    # ---- Variables
    # We are not using variable mixin because we don't need to parse values
    variable_value_ids = fields.One2many(
        string="Variable Values",
        comodel_name="cx.tower.variable.value",
        auto_join=True,
        inverse_name="server_template_id",
    )
