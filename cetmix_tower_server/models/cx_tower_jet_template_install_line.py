from odoo import fields, models


class CxTowerJetTemplateInstallLine(models.Model):
    """
    Used to track the order and status of templates to install/uninstall.
    """

    _name = "cx.tower.jet.template.install.line"
    _description = "Jet Template Install/Uninstall Line"
    _order = "order desc"

    order = fields.Integer()
    jet_template_install_id = fields.Many2one(
        comodel_name="cx.tower.jet.template.install",
        ondelete="cascade",
    )
    jet_template_id = fields.Many2one(
        comodel_name="cx.tower.jet.template",
        ondelete="cascade",
    )
    server_id = fields.Many2one(
        comodel_name="cx.tower.server",
        related="jet_template_install_id.server_id",
        readonly=True,
    )
    state = fields.Selection(
        selection=[
            ("t", "To Install"),
            ("p", "Processing"),
            ("i", "Installed"),
            ("f", "Failed"),
        ],
        default="t",
    )
