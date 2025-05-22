# Copyright 2025 Cetmix OÜ
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0)

from odoo import api, fields, models


class CxTowerJetTemplateInstallWizard(models.TransientModel):
    """
    Wizard to install a Jet Template on selected servers.
    """

    _name = "cx.tower.jet.template.install.wiz"
    _description = "Install Jet Template on Selected Servers"

    jet_template_id = fields.Many2one(
        "cx.tower.jet.template",
        required=True,
    )
    server_ids = fields.Many2many(
        "cx.tower.server",
        string="Servers",
    )
    server_domain = fields.Binary(
        compute="_compute_server_domain",
    )

    @api.depends("jet_template_id")
    def _compute_server_domain(self):
        for wizard in self:
            servers_installed = wizard.jet_template_id.server_ids
            wizard.server_domain = (
                [("id", "not in", servers_installed.ids)] if servers_installed else []
            )

    def action_install_template(self):
        """
        Install the Jet Template on the selected servers.
        """
        self.jet_template_id.install_on_servers(self.server_ids)
