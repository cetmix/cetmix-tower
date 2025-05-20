# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CxTowerServerJetTemplateInstallWizard(models.TransientModel):
    """Wizard to install jet templates on servers"""

    _name = "cx.tower.server.jet.template.install.wizard"
    _description = "Install Jet Template on Server"

    server_ids = fields.Many2many(
        "cx.tower.server",
        string="Servers",
        required=True,
        help="Servers where the jet template will be installed",
    )

    jet_template_id = fields.Many2one(
        "cx.tower.jet.template",
        string="Jet Template",
        required=True,
        help="Jet template to install",
    )

    def action_install_template(self):
        """Install the selected jet template on servers"""
        self.ensure_one()
