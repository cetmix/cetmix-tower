from odoo import fields, models


class CxTowerJetTemplateInstallLine(models.Model):
    """
    Used to track the order and status of templates to install/uninstall.
    """

    _name = "cx.tower.jet.template.install.line"
    _description = "Jet Template Install/Uninstall Line"
    _order = "order"
    _rec_name = "jet_template_id"

    order = fields.Integer(required=True, default=10)
    jet_template_install_id = fields.Many2one(
        comodel_name="cx.tower.jet.template.install",
        ondelete="cascade",
        required=True,
        index=True,
    )
    jet_template_id = fields.Many2one(
        comodel_name="cx.tower.jet.template",
        ondelete="cascade",
        required=True,
        index=True,
    )
    server_id = fields.Many2one(
        comodel_name="cx.tower.server",
        related="jet_template_install_id.server_id",
        readonly=True,
        store=True,
    )
    state = fields.Selection(
        selection=[
            ("to_process", "To Process"),
            ("processing", "Processing"),
            ("done", "Done"),
            ("failed", "Failed"),
        ],
        default="to_process",
    )
