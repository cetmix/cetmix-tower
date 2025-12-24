# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from ansi2html import Ansi2HTMLConverter

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from ..models.tools import generate_random_id

html_converter = Ansi2HTMLConverter(inline=True)


class CxTowerCommandRunWizard(models.TransientModel):
    """
    Wizard to run a command on selected servers.
    """

    _name = "cx.tower.command.run.wizard"
    _inherit = "cx.tower.template.mixin"
    _description = "Run Command in Wizard"

    server_ids = fields.Many2many(
        "cx.tower.server",
        string="Servers",
    )
    command_id = fields.Many2one(
        "cx.tower.command",
    )
    note = fields.Text(related="command_id.note", readonly=True)
    action = fields.Selection(
        selection=[
            ("ssh_command", "SSH command"),
            ("python_code", "Python code"),
        ],
        default="ssh_command",
        required=True,
    )
    path = fields.Char(
        compute="_compute_code",
        readonly=False,
        store=True,
        help="Put custom path to run the command.\n"
        "IMPORTANT: this field does NOT support variables!",
    )
    command_domain = fields.Binary(
        compute="_compute_command_domain",
    )
    tag_ids = fields.Many2many(
        comodel_name="cx.tower.tag",
        string="Tags",
    )
    use_sudo = fields.Boolean(
        string="Use sudo",
        help="Will use sudo based on server settings."
        "If no sudo is configured will run without sudo",
    )
    code = fields.Text(compute="_compute_code", readonly=False, store=True)
    applicability = fields.Selection(
        selection=[
            ("this", "For selected server(s)"),
            ("shared", "Non server restricted"),
        ],
        default="shared",
        required=True,
        compute="_compute_show_servers",
        readonly=False,
        store=True,
        help="Selected server(s): only Commands that are specific"
        " to the selected server(s)\n"
        "Non server restricted: all Commands that are "
        "not specific to any server",
    )
    rendered_code = fields.Text(
        compute="_compute_rendered_code",
        compute_sudo=True,
    )
    result = fields.Html()
    show_servers = fields.Boolean(
        compute="_compute_show_servers",
        store=True,
    )
    os_compatibility_warning = fields.Text(
        compute="_compute_os_compatibility_warning",
        compute_sudo=True,
        help="Warning about OS compatibility of the command",
    )
    command_variable_ids = fields.Many2many(
        "cx.tower.variable",
        related="command_id.variable_ids",
        readonly=True,
        string="Command Variables",
    )
    custom_variable_value_ids = fields.One2many(
        "cx.tower.command.run.wizard.variable.value",
        "wizard_id",
    )
    have_access_to_server = fields.Boolean(
        compute="_compute_have_access_to_server",
    )
    has_missing_required_values = fields.Boolean(
        compute="_compute_has_missing_required_values"
    )
    missing_required_variables_message = fields.Text(
        compute="_compute_has_missing_required_values"
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if not self._is_privileged_user():
            res["applicability"] = "this"
        return res

    @api.depends("server_ids")
    def _compute_show_servers(self):
        for rec in self:
            rec.show_servers = bool(rec.server_ids and len(rec.server_ids) > 1)

    @api.depends("command_id", "server_ids", "action")
    def _compute_code(self):
        """
        Set code after change command
        """
        for record in self:
            if record.command_id and record.server_ids:
                # Render code preview for the first server only.
                record.update(
                    {
                        "code": record.command_id.code,
                        "path": record.server_ids[0]
                        ._render_command(record.command_id)
                        .get("rendered_path"),
                    }
                )
            else:
                record.update({"code": False, "path": False})

    @api.depends("code", "server_ids", "action", "custom_variable_value_ids.value_char")
    def _compute_rendered_code(self):
        for record in self:
            if record.server_ids and len(record.server_ids) == 1:
                # Render code preview for the first server only.
                server_id = record.server_ids[0]

                # Get variable list
                variables = record.get_variables()

                # Get variable values
                variable_values = server_id.get_variable_values(
                    variables.get(str(record.id))
                )
                if variable_values and record.custom_variable_value_ids:
                    custom_vals = {
                        custom_value.variable_id.reference: custom_value.value_char
                        for custom_value in record.custom_variable_value_ids
                        if custom_value.variable_id
                    }
                    variable_values[server_id.id].update(custom_vals)

                # Render template
                if variable_values:
                    record.rendered_code = record.render_code(
                        pythonic_mode=record.action == "python_code",
                        **variable_values.get(server_id.id),
                    ).get(self.id)  # pylint: disable=no-member
                else:
                    record.rendered_code = record.code
            else:
                record.rendered_code = record.code

    @api.depends("applicability", "server_ids", "tag_ids", "action")
    def _compute_command_domain(self):
        """
        Compose domain based on condition
        """
        for record in self:
            domain = [("action", "=", record.action)]
            if record.applicability == "shared":
                domain.append(("server_ids", "=", False))
            elif record.applicability == "this":
                domain.append(("server_ids", "in", record.server_ids.ids))
            if record.tag_ids:
                domain.append(("tag_ids", "in", record.tag_ids.ids))
            record.command_domain = domain

    @api.depends("command_id", "server_ids")
    def _compute_os_compatibility_warning(self):
        for wizard in self:
            # Skip if command is not SSH command or no OS compatibility is defined
            if (
                not wizard.command_id
                or not wizard.server_ids
                or wizard.command_id.action != "ssh_command"
                or not wizard.command_id.os_ids
            ):
                wizard.os_compatibility_warning = False
                continue
            warning_list = []
            for server in wizard.server_ids:
                if server.os_id not in wizard.command_id.os_ids:
                    warning_list.append(
                        _(
                            "OS %(os)s used by the server '%(srv)s' is not present"
                            " in the command's OS compatibility list",
                            os=server.os_id.name,
                            srv=server.name,
                        )
                    )
            wizard.os_compatibility_warning = (
                "\n".join(warning_list) if warning_list else False
            )

    @api.depends("server_ids")
    def _compute_have_access_to_server(self):
        """
        Compute have_access_to_server field
        """
        for record in self:
            if not record.server_ids:
                record.have_access_to_server = False
                continue
            record.have_access_to_server = all(
                server._have_access_to_server("write") for server in record.server_ids
            )

    @api.depends(
        "custom_variable_value_ids.value_char",
        "custom_variable_value_ids.required",
    )
    def _compute_has_missing_required_values(self):
        """
        Mark the wizard when at least one *required* variable
        has an empty value **and** build a human-readable message.
        """
        for wiz in self:
            missing = wiz.custom_variable_value_ids.filtered(
                lambda var_line: var_line.required and not var_line.value_char
            )
            wiz.has_missing_required_values = bool(missing)
            wiz.missing_required_variables_message = (
                _(
                    "Please provide values for the following "
                    "configuration variables: %(vars)s",
                    vars=", ".join(missing.mapped("variable_id.name")),
                )
                if missing
                else False
            )

    @api.onchange("action", "applicability")
    def _onchange_action(self):
        """
        Reset command after change action
        """
        self.command_id = False

    @api.onchange("command_variable_ids", "server_ids")
    def _onchange_command_variable_ids(self):
        """
        Reset custom variable values after change code
        """
        # Remove existing custom variable values
        self.custom_variable_value_ids = False

        if (
            not self.command_variable_ids
            or not self.server_ids
            or len(self.server_ids) > 1
        ):
            return

        # Add new custom variable values
        # Render values for the first server only.
        server_id = self.server_ids

        # Get variable list
        variables = self.get_variables()

        # Get variable values
        variable_values = server_id.get_variable_values(variables.get(str(self.id)))[
            server_id.id
        ]

        # Filter variables current user has access to
        command_variables = self.command_variable_ids.search(
            [("id", "in", self.command_variable_ids.ids)]
        )

        self.custom_variable_value_ids = [
            (
                0,
                0,
                {
                    "variable_id": variable.id,
                    "value_char": variable_values.get(variable.reference),
                    "option_id": variable.option_ids.filtered(
                        lambda o, v=variable: o.value_char
                        == variable_values.get(v.reference)
                    ).id
                    if variable.variable_type == "o"
                    else None,
                    "variable_value_id": server_id.variable_value_ids.filtered(
                        lambda v, var=variable: v.variable_id == var
                    )[:1].id,
                },
            )
            for variable in command_variables
        ]

    def action_run_command(self):
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
            "name": _("Run Command"),
            "res_model": "cx.tower.command.run.wizard",
            "view_mode": "form",
            "target": "new",
            "context": context,
        }

    def run_command_on_server(self):
        """Run command on selected servers"""
        # Check if all required values are set
        if self.has_missing_required_values:
            raise ValidationError(self.missing_required_variables_message)
        # Check if command is selected
        if not self.command_id:
            raise ValidationError(_("Please select a command to execute"))
        # Generate custom label. Will be used later to locate the command log
        log_label = generate_random_id(4)
        path_value = (
            self.env.user.has_group("cetmix_tower_server.group_manager") and self.path
        )
        # Add custom values for log
        kwargs = {
            "log": {"label": log_label},
            "variable_values": {
                value.variable_id.reference: value.value_char
                for value in self.custom_variable_value_ids
            },
        }
        for server in self.server_ids:
            server.run_command(
                self.command_id,
                sudo=self.use_sudo,
                path=path_value,
                **kwargs,
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Command Log"),
            "res_model": "cx.tower.command.log",
            "view_mode": "list,form",
            "target": "current",
            "context": {"search_default_label": log_label},
        }

    def run_command_in_wizard(self):
        """
        Runs a given code as is in wizard
        """
        # Check if multiple servers are selected
        if len(self.server_ids) > 1:
            raise ValidationError(
                _("You cannot run custom code on multiple servers at once.")
            )

        # Raise access error if non manager is trying to call this method
        if not self.env.user.has_group(
            "cetmix_tower_server.group_manager"
        ) and not self.env.user.has_group("cetmix_tower_server.group_root"):
            raise AccessError(_("You are not allowed to execute commands in wizard"))

        self.ensure_one()

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
                    _("Another instance of the command is already running")
                )

        if not self.rendered_code:
            raise ValidationError(_("You cannot execute an empty command"))

        # check that we can execute the command for selected servers
        command_servers = self.command_id.server_ids
        if command_servers and not all(
            [server in command_servers for server in self.server_ids]
        ):
            raise ValidationError(_("Some servers don't support this command"))

        result = ""

        # Set the "no_split_for_sudo" property
        if self.command_id and self.command_id.no_split_for_sudo:
            no_split_for_sudo = True
        else:
            no_split_for_sudo = False

        for server in self.server_ids:
            server_name = server.name
            # Prepare key renderer values
            key_vals = {
                "server_id": server.id,
                "partner_id": server.partner_id.id if server.partner_id else None,
            }

            kwargs = {
                "key": key_vals,
                "no_split_for_sudo": no_split_for_sudo,
            }

            if self.action == "python_code":
                command_result = server._run_python_code(
                    code=self.rendered_code, **kwargs
                )
            else:
                command_result = server._run_command_using_ssh(
                    server._get_ssh_client(raise_on_error=True),
                    self.rendered_code,
                    self.path or None,
                    sudo=self.use_sudo and server.use_sudo,
                    **kwargs,
                )
            command_error = command_result["error"]
            command_response = command_result["response"]
            if command_error:
                result = f"{result}\n[{server_name}]: ERROR: {command_error}"
            if command_response:
                result = f"{result}\n[{server_name}]: {command_response}"
            if not result.endswith("\n"):
                result = f"{result}\n"

        if result:
            self.result = html_converter.convert(result)
            return {
                "type": "ir.actions.act_window",
                "name": _("Run Result"),
                "res_model": "cx.tower.command.run.wizard",
                "res_id": self.id,  # pylint: disable=no-member
                "view_mode": "form",
                "target": "new",
            }

    def _is_privileged_user(self):
        """Return True if current user is in Manager or Root group."""
        return self.env.user.has_group(
            "cetmix_tower_server.group_manager"
        ) or self.env.user.has_group("cetmix_tower_server.group_root")


class CxTowerCommandRunWizardVariableValue(models.TransientModel):
    """
    Custom variable values for command run wizard
    """

    _inherit = "cx.tower.custom.variable.value.mixin"
    _name = "cx.tower.command.run.wizard.variable.value"
    _description = "Custom variable values for command run wizard"

    variable_id = fields.Many2one(
        readonly=True,
    )
    wizard_id = fields.Many2one(
        "cx.tower.command.run.wizard",
        string="Wizard",
    )
