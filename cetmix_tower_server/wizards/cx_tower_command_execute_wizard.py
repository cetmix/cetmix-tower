from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..models.tools import generate_random_id


class CxTowerCommandExecuteWizard(models.TransientModel):
    _name = "cx.tower.command.execute.wizard"
    _inherit = "cx.tower.template.mixin"
    _description = "Execute Command in Wizard"

    server_ids = fields.Many2many(
        "cx.tower.server",
        string="Servers",
    )
    command_id = fields.Many2one(
        "cx.tower.command",
        required=True,
    )
    tag_ids = fields.Many2many(
        comodel_name="cx.tower.tag",
        relation="cx_tower_command_execute_tag_rel",
        column1="wizard_id",
        column2="tag_id",
        string="Tags",
    )
    use_sudo = fields.Selection(
        string="Use sudo",
        selection=[("n", "Without password"), ("p", "With password")],
        help="Run commands using 'sudo'",
    )
    any_server = fields.Boolean()
    rendered_code = fields.Text()
    result = fields.Text()

    @api.onchange("command_id")
    def _onchange_command_id(self):
        """
        Set code after change command
        """
        if self.command_id and self.server_ids:
            self.code = self.command_id.code

    @api.onchange("code", "server_ids")
    def _onchange_code(self):
        if self.server_ids:
            server_id = self.server_ids[0]  # TODO testing only!!!

            # Get variable list
            variables = self.get_variables()

            # Get variable values
            variable_values = server_id.get_variable_values(variables.get(self.id))

            # Render template
            if variable_values:
                self.rendered_code = self.render_code(
                    **variable_values.get(server_id.id)
                ).get(self.id)
            else:
                self.rendered_code = self.code

    @api.onchange("any_server", "server_ids", "tag_ids")
    def _onchange_tag_ids(self):
        """Compose domain based on condition
        - any server: show commands compatible with any server
        """

        domain = []
        if self.any_server:
            domain = [("server_ids", "=", False)]
        elif self.server_ids:
            domain.append(("server_ids", "in", self.server_ids.ids))
        if self.tag_ids:
            domain.append(("tag_ids", "in", self.tag_ids.ids))

        return {"domain": {"command_id": domain}}

    def action_execute_command(self):
        """
        Return wizard action to select command and execute it
        """
        context = self.env.context.copy()
        context.update(
            {
                "default_server_ids": self.server_ids.ids,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Execute Command"),
            "res_model": "cx.tower.command.execute.wizard",
            "view_mode": "form",
            "view_type": "form",
            "target": "new",
            "context": context,
        }

    def execute_command_on_server(self):
        """Render selected command rendered using server method"""

        # Generate custom label. Will be used later to locate the command log
        log_label = generate_random_id(4)
        # Add custom values for log
        custom_values = {"log": {"label": log_label}}
        self.server_ids.execute_commands(
            self.command_id, sudo=self.use_sudo, **custom_values
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Command Log"),
            "res_model": "cx.tower.command.log",
            "view_mode": "tree,form",
            "target": "current",
            "context": {"search_default_label": log_label},
        }

    def execute_command(self):
        """
        Executes a given code as is in wizard
        """
        self.ensure_one()
        code = self.code
        if not code:
            raise ValidationError(_("You cannot execute empty command."))

        # check that we can execute the command for selected servers
        command_servers = self.command_id.server_ids
        if command_servers and not all(
            [server in command_servers for server in self.server_ids]
        ):
            raise ValidationError(_("Some servers don't support this command."))

        result = ""

        for server in self.server_ids:

            server_name = server.name
            client = server._connect(raise_on_error=True)
            status, response, error = server._execute_command(
                client, self.rendered_code, sudo=self.use_sudo
            )
            for err in error:
                result += "[{server}]: ERROR: {err}".format(server=server_name, err=err)
            for res in response:
                result += "[{server}]: {res}".format(server=server_name, res=res)
            if not result.endswith("\n"):
                result += "\n"
            result += "\n"

        if result:
            self.result = result
            return {
                "type": "ir.actions.act_window",
                "name": _("Execute Result"),
                "res_model": "cx.tower.command.execute.wizard",
                "res_id": self.id,
                "view_mode": "form",
                "view_type": "form",
                "target": "new",
            }
