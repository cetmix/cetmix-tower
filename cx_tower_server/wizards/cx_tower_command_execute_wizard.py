from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.osv import expression


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
    show_all = fields.Boolean(default=False)
    available_server_tag_ids = fields.Many2many(
        comodel_name="cx.tower.tag",
        relation="cx_tower_command_execute_tag_rel",
        column1="wizard_id",
        column2="tag_id",
        string="Tags",
        compute="_compute_available_server_tag_ids",
    )
    rendered_code = fields.Text()
    result = fields.Text()

    @api.onchange("command_id")
    def _onchange_command_id(self):
        """
        Set code after change command
        """
        if self.command_id and self.server_ids:
            self.code = self.command_id.code

    @api.onchange("code")
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

    @api.depends("show_all", "server_ids")
    def _compute_available_server_tag_ids(self):
        """
        Compute available tags by selected servers and `show_all` parameter
        """
        self.ensure_one()
        domain = [("server_ids", "in", self.server_ids.ids)]
        if self.show_all:
            domain = expression.OR([domain, [("server_ids", "=", False)]])
        self.available_server_tag_ids = self.env["cx.tower.tag"].search(domain)

    def execute_command(self):
        """
        Executes a given code
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

        variables = self.get_variables()
        # Get variable values
        variable_values = self.server_ids.get_variable_values(variables.get(self.id))

        for server in self.server_ids:

            # Render template with values
            if variable_values:
                rendered_code = self.render_code(**variable_values.get(server.id)).get(
                    self.id
                )
            else:
                rendered_code = self.code

            server_name = server.name
            client = server._connect(raise_on_error=True)
            status, response, error = server._execute_command(client, rendered_code)
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
