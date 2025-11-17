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
    jet_template_domain = fields.Binary(
        compute="_compute_jet_template_domain",
    )
    server_domain = fields.Binary(
        compute="_compute_server_domain",
    )

    @api.depends("server_ids", "server_ids.jet_template_ids")
    def _compute_jet_template_domain(self):
        """
        Show only templates that are not installed on the selected server.
        """
        for wizard in self:
            if wizard.server_ids and len(wizard.server_ids) == 1:
                server = wizard.server_ids[0]
                templates_installed = server.jet_template_ids
                wizard.jet_template_domain = [("id", "not in", templates_installed.ids)]
            else:
                wizard.jet_template_domain = []

    @api.depends("jet_template_id", "jet_template_id.server_ids")
    def _compute_server_domain(self):
        """
        Show only servers where the template is not installed.
        """
        for wizard in self:
            if wizard.jet_template_id:
                servers_installed = wizard.jet_template_id.server_ids
                wizard.server_domain = (
                    [("id", "not in", servers_installed.ids)]
                    if servers_installed
                    else []
                )
            else:
                wizard.server_domain = []

    def action_install_template(self):
        """
        Install the Jet Template on the selected servers.
        """
        if self.server_ids:
            self.jet_template_id.install_on_servers(self.server_ids)

        # Close the wizard
        return {
            "type": "ir.actions.act_window_close",
            "params": {
                "next": {"type": "ir.actions.client", "tag": "soft_reload"},
            },
        }
