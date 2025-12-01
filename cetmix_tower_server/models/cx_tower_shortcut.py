# Copyright (C) 2024 Cetmix OÜ
# License OPL-1 (https://apps.odoocdn.com/loempia/static/examples/LICENSE).
from odoo import _, fields, models


class CxTowerShortcut(models.Model):
    """
    Cetmix Tower Shortcut.
    Used to run commands or flight plans with a single click.
    """

    _name = "cx.tower.shortcut"
    _inherit = ["cx.tower.access.mixin", "cx.tower.reference.mixin"]
    _description = "Cetmix Tower Shortcut"
    _order = "sequence, name"

    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    server_ids = fields.Many2many(
        string="Servers",
        comodel_name="cx.tower.server",
        relation="cx_tower_server_shortcut_rel",
        column1="shortcut_id",
        column2="server_id",
    )
    server_template_ids = fields.Many2many(
        string="Server Templates",
        comodel_name="cx.tower.server.template",
        relation="cx_tower_server_template_shortcut_rel",
        column1="shortcut_id",
        column2="server_template_id",
    )
    action = fields.Selection(
        selection=[("command", "Command"), ("plan", "Flight Plan")], required=True
    )
    command_id = fields.Many2one(comodel_name="cx.tower.command")
    use_sudo = fields.Boolean(
        help="Run command using 'sudo'",
    )
    plan_id = fields.Many2one(string="Flight Plan", comodel_name="cx.tower.plan")
    note = fields.Text()

    def run(self, server=None):
        """Runs related shortcut action

        Args:
            server (cx.tower.server): Server to run the shortcut.
        """
        self.ensure_one()

        # Try to obtain server from context if not provided as an argument
        if server is None:
            server_id = self.env.context.get("server_id")

            # Just return, no exceptions for now
            if not server_id:
                return

            server = self.env["cx.tower.server"].browse(server_id)

            # Just return, no exceptions for now
            if not server:
                return

        # Use the first server record if several are passed
        if len(server) > 1:
            server = server[0]
        if self.action == "command" and self.command_id:
            server.run_command(self.sudo().command_id, sudo=self.use_sudo)
        elif self.action == "plan" and self.plan_id:
            server.run_flight_plan(self.sudo().plan_id)

        # Notify
        return self._notify_on_run(server)

    def _notify_on_run(self, server):
        """Send notification when shortcut is triggered.
        Override to implement custom notifications.

        Args:
            server (cx.tower.server()): Server action was triggered for

        Returns:
            Boolean: True if notification was sent.
        """
        self.ensure_one()

        self.env.user.notify_info(
            title=server.name,
            message=_(
                "Shortcut '%(shr)s' triggered. Check %(t)s log for result",
                shr=self.name,
                t="flight plan" if self.action == "plan" else "command",
            ),
            sticky=False,
        )
        return True
