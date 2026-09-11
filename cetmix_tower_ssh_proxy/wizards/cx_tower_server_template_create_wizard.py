from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CxTowerServerTemplateCreateWizard(models.TransientModel):
    _inherit = "cx.tower.server.template.create.wizard"

    ssh_connection_route = fields.Selection(
        selection=[
            ("direct", "Direct"),
            ("proxy", "SSH Proxy"),
        ],
        string="SSH Connection Route",
        default="direct",
        required=True,
    )
    ssh_proxy_server_id = fields.Many2one(
        comodel_name="cx.tower.server",
        string="SSH Proxy Server",
        ondelete="set null",
    )

    @api.onchange("ssh_connection_route")
    def _onchange_ssh_connection_route(self):
        """
        When the SSH connection route is changed to direct,
        the SSH proxy server must be cleared
        """
        for wizard in self:
            if wizard.ssh_connection_route == "direct":
                wizard.ssh_proxy_server_id = False

    @api.onchange("ssh_proxy_server_id")
    def _onchange_ssh_proxy_server_id(self):
        """
        When the SSH proxy server is changed,
        the SSH connection route must be set to proxy
        """
        for wizard in self:
            if wizard.ssh_proxy_server_id:
                wizard.ssh_connection_route = "proxy"

    @api.constrains("ssh_connection_route", "ssh_proxy_server_id")
    def _check_ssh_proxy_configuration(self):
        """
        Check that the SSH proxy configuration is valid
        """
        for wizard in self:
            if (
                wizard.ssh_connection_route == "proxy"
                and not wizard.ssh_proxy_server_id
            ):
                raise ValidationError(
                    _(
                        "SSH Proxy Server is required when SSH Connection Route "
                        "is Proxy."
                    )
                )
            if wizard.ssh_connection_route == "direct" and wizard.ssh_proxy_server_id:
                raise ValidationError(
                    _(
                        "SSH Proxy Server must be empty when SSH Connection Route "
                        "is Direct."
                    )
                )

    def _prepare_server_parameters(self):
        """
        Override the server parameters to include the SSH proxy configuration
        """
        result = super()._prepare_server_parameters()
        result.update(
            {
                "ssh_connection_route": self.ssh_connection_route,
                "ssh_proxy_server_id": self.ssh_proxy_server_id.id,
            }
        )
        return result
