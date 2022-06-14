from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CxTowerCommandExecuteWizard(models.TransientModel):
    _name = "cx.tower.command.execute.wizard"
    _inherit = "cx.tower.template.mixin"
    _description = "Execute Command in Wizard"

    @api.onchange("command_id")
    def _onchange_command_id(self):
        """
        Set code after change command
        """
        if self.command_id and self.server_ids:
            self.code = self.command_id.code
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

    @api.model
    def _domain_command_id(self):
        """
        Return domain to select commands available for selected servers
        """
        return "['|', ('server_ids', '=', False), ('server_ids', 'in', server_ids)]"

    server_ids = fields.Many2many(
        "cx.tower.server",
        string="Servers",
    )
    command_id = fields.Many2one(
        "cx.tower.command",
        domain=lambda self: self._domain_command_id(),
        required=True,
    )
    rendered_code = fields.Text()
    result = fields.Text()

    def execute_command(self):
        """
        Executes a given code
        """
        self.ensure_one()
        code = self.rendered_code  # TODO testing POC!!
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
            status, response = server._execute_command(client, code)
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
