from odoo import fields, models


class CxTowerJetTemplateInstallLine(models.Model):
    """
    Used to track the order and status of templates to install/uninstall.
    """

    _name = "cx.tower.jet.template.install.line"
    _description = "Jet Template Install/Uninstall Line"
    _log_access = False
    _order = "order desc"

    jet_template_install_id = fields.Many2one(
        comodel_name="cx.tower.jet.template.install",
        ondelete="cascade",
    )
    jet_template_id = fields.Many2one(
        comodel_name="cx.tower.jet.template",
        ondelete="cascade",
    )
    installed = fields.Boolean(
        default=False,
    )
    state = fields.Selection(
        selection=[
            ("t", "To Install"),
            ("i", "Installing"),
            ("d", "Done"),
            ("f", "Failed"),
        ],
        default="t",
    )
    order = fields.Integer()
