from odoo import _, models
from odoo.exceptions import AccessError


class IrActionsServer(models.Model):
    _inherit = "ir.actions.server"

    def run(self):
        """
        We override this method to return more
        user friendly error messages.
        """
        if self.sudo().model_name == "cx.tower.server":
            try:
                res = super().run()
                return res
            except AccessError as e:
                raise AccessError(
                    _(
                        "You need to have 'write' access to all servers "
                        "you want to run this action on."
                    )
                ) from e
        return super().run()
