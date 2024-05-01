# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
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
    command_domain = fields.Binary(
        compute="_compute_command_domain",
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
        selection=[("n", "Sudo without password"), ("p", "Sudo with password")],
        help="Run commands using 'sudo'",
    )
    code = fields.Text(
        compute="_compute_code",
        readonly=False,
    )
    any_server = fields.Boolean()
    rendered_code = fields.Text(
        compute="_compute_rendered_code",
    )
    result = fields.Text()

    @api.depends("command_id", "server_ids")
    def _compute_code(self):
        """
        Set code after change command
        """
        for record in self:
            if record.command_id and record.server_ids:
                record.code = record.command_id.code
            else:
                record.code = record.code

    @api.depends("code", "server_ids")
    def _compute_rendered_code(self):
        for record in self:
            if record.server_ids:
                server_id = record.server_ids[0]  # TODO testing only!!!

                # Get variable list
                variables = record.get_variables()

                # Get variable values
                variable_values = server_id.get_variable_values(
                    variables.get(str(record.id))
                )

                # Render template
                if variable_values:
                    record.rendered_code = record.render_code(
                        **variable_values.get(server_id.id)
                    ).get(self.id)
                else:
                    record.rendered_code = record.code
            else:
                record.rendered_code = record.code

    @api.depends("any_server", "server_ids", "tag_ids")
    def _compute_command_domain(self):
        """Compose domain based on condition
        - any server: show commands compatible with any server
        """
        for record in self:
            domain = []
            if record.any_server:
                domain = [("server_ids", "=", False)]
            elif record.server_ids:
                domain.append(("server_ids", "in", record.server_ids.ids))
            if record.tag_ids:
                domain.append(("tag_ids", "in", record.tag_ids.ids))
            record.command_domain = domain

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
        custom_values = {"log": {"label": log_label}, "show_notification": True}
        return self.server_ids.execute_commands(
            self.command_id, sudo=self.use_sudo, **custom_values
        )

    def execute_command(self):
        """
        Executes a given code as is in wizard
        """
        if not self.command_id.allow_parallel_run:
            running_count = (
                self.env["cx.tower.command.log"]
                .sudo()
                .search_count(
                    [
                        ("server_id", "in", self.server_ids.ids),
                        ("command_id", "=", self.command_id.id),
                        ("is_running", "=", True),
                    ]
                )
            )
            # Create log record and continue to the next one
            # if the same command is currently running on the same server
            # Log result
            if running_count > 0:
                raise ValidationError(
                    _("Another instance of the command is running already")
                )

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
