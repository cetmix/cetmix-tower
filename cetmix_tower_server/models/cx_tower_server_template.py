# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CxTowerServerTemplate(models.Model):
    """Server Template. Used to simplify server creation"""

    _name = "cx.tower.server.template"
    _inherit = [
        "cx.tower.reference.mixin",
        "mail.thread",
        "mail.activity.mixin",
        "cx.tower.access.role.mixin",
        "cx.tower.tag.mixin",
    ]
    _description = "Cetmix Tower Server Template"
    _order = "name"

    active = fields.Boolean(default=True)

    # --- Connection
    ssh_port = fields.Integer(string="SSH port", default=22)
    ssh_username = fields.Char(string="SSH Username")
    ssh_password = fields.Char(string="SSH Password")
    ssh_key_id = fields.Many2one(
        comodel_name="cx.tower.key",
        string="SSH Private Key",
        domain=[("key_type", "=", "k")],
    )
    ssh_auth_mode = fields.Selection(
        string="SSH Auth Mode",
        selection=[
            ("p", "Password"),
            ("k", "Key"),
        ],
    )
    use_sudo = fields.Selection(
        string="Use sudo",
        selection=[("n", "Without password"), ("p", "With password")],
        help="Run commands using 'sudo'",
    )

    # --- Attributes
    color = fields.Integer(help="For better visualization in views")
    os_id = fields.Many2one(string="Operating System", comodel_name="cx.tower.os")
    tag_ids = fields.Many2many(
        relation="cx_tower_server_template_tag_rel",
        column1="server_template_id",
        column2="tag_id",
    )

    # --- Variables
    # We are not using variable mixin because we don't need to parse values
    variable_value_ids = fields.One2many(
        string="Variable Values",
        comodel_name="cx.tower.variable.value",
        auto_join=True,
        inverse_name="server_template_id",
    )

    # --- Server logs
    server_log_ids = fields.One2many(
        comodel_name="cx.tower.server.log", inverse_name="server_template_id"
    )

    # --- Shortcuts
    shortcut_ids = fields.Many2many(
        comodel_name="cx.tower.shortcut",
        relation="cx_tower_server_template_shortcut_rel",
        column1="server_template_id",
        column2="shortcut_id",
        string="Shortcuts",
    )

    # --- Scheduled Tasks
    scheduled_task_ids = fields.Many2many(
        comodel_name="cx.tower.scheduled.task",
        relation="cx_tower_server_template_scheduled_task_rel",
        column1="server_template_id",
        column2="scheduled_task_id",
        string="Scheduled Tasks",
    )

    # --- Flight Plan
    flight_plan_id = fields.Many2one(
        "cx.tower.plan",
        help="This flight plan will be run upon server creation",
        domain="[('server_ids', '=', False)]",
    )

    # ---- Delete plan
    plan_delete_id = fields.Many2one(
        "cx.tower.plan",
        string="On Delete Plan",
        groups="cetmix_tower_server.group_manager",
        help="This Flightplan will be executed when the server is deleted",
    )

    # --- Created Servers
    server_ids = fields.One2many(
        comodel_name="cx.tower.server",
        inverse_name="server_template_id",
    )
    server_count = fields.Integer(
        compute="_compute_server_count",
    )

    # -- Other
    note = fields.Text()

    # ---- Access. Add relation for mixin fields
    user_ids = fields.Many2many(
        relation="cx_tower_server_template_user_rel",
        domain=lambda self: [
            ("groups_id", "in", [self.env.ref("cetmix_tower_server.group_manager").id])
        ],
    )
    manager_ids = fields.Many2many(
        relation="cx_tower_server_template_manager_rel",
    )

    @api.depends("server_ids")
    def _compute_server_count(self):
        """
        Compute total server counts created from the templates
        """
        for template in self:
            template.server_count = len(template.server_ids)

    def copy(self, default=None):
        """Duplicate the server template along with variable values and server logs."""
        default = dict(default or {})

        # Duplicate the server template itself
        new_template = super().copy(default)

        # Duplicate variable values
        for variable_value in self.variable_value_ids:
            variable_value.with_context(reference_mixin_skip_self=True).copy(
                {"server_template_id": new_template.id}
            )

        # Duplicate server logs
        for server_log in self.server_log_ids:
            server_log.copy({"server_template_id": new_template.id})

        return new_template

    def action_create_server(self):
        """
        Returns wizard action to create new server
        """
        self.ensure_one()
        context = self.env.context.copy()
        context.update(
            {
                "default_server_template_id": self.id,  # pylint: disable=no-member
                "default_color": self.color,
                "default_ssh_port": self.ssh_port,
                "default_ssh_username": self.ssh_username,
                "default_ssh_password": self.ssh_password,
                "default_ssh_key_id": self.ssh_key_id.id,
                "default_ssh_auth_mode": self.ssh_auth_mode,
                "default_plan_delete_id": self.plan_delete_id.id,
            }
        )
        if self.variable_value_ids:
            context.update(
                {
                    "default_line_ids": [
                        (
                            0,
                            0,
                            {
                                "variable_value_id": line.id,
                            },
                        )
                        for line in self.variable_value_ids
                    ]
                }
            )
        return {
            "type": "ir.actions.act_window",
            "name": _("Create Server"),
            "res_model": "cx.tower.server.template.create.wizard",
            "view_mode": "form",
            "target": "new",
            "context": context,
        }

    def action_open_servers(self):
        """
        Return action to open related servers
        """
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_server"
        )
        action.update(
            {
                "domain": [("server_template_id", "=", self.id)],  # pylint: disable=no-member
            }
        )
        return action

    @api.model
    def create_server_from_template(self, template_reference, server_name, **kwargs):
        """This is a wrapper function that is meant to be called
        when we need to create a server from specific server template

        Args:
            template_reference (Char): Server template reference
            server_name (Char): Name of the new server

        Kwargs:
            partner (res.partner(), optional): Partner this server belongs to.
            ipv4 (Char, optional): IP v4 address. Defaults to None.
            ipv6 (Char, optional): IP v6 address.
                Must be provided in case IP v4 is not. Defaults to None.
            ssh_password (Char, optional): SSH password. Defaults to None.
            ssh_key (Char, optional): SSH private key record reference.
                Defaults to None.
            configuration_variables (Dict, optional): Custom configuration variable.
                Following format is used:
                    `variable_reference`: `variable_value_char`
                    eg:
                    {'branch': 'prod', 'odoo_version': '16.0'}
            pick_all_template_variables (bool):  This parameter ensures that the server
                being created considers existing variables from the template.
                If enabled, the template variables will also be included in the server
                variables. The default value is True.

        Returns:
            cx.tower.server: newly created server record
        """
        template = self.get_by_reference(template_reference)
        return template._create_new_server(server_name, **kwargs)

    def _create_new_server(self, name, **kwargs):
        """Creates a new server from template

        Args:
            name (Char): Name of the new server

        Kwargs:
            partner (res.partner(), optional): Partner this server belongs to.
            ipv4 (Char, optional): IP v4 address. Defaults to None.
            ipv6 (Char, optional): IP v6 address.
                Must be provided in case IP v4 is not. Defaults to None.
            ssh_password (Char, optional): SSH password. Defaults to None.
            ssh_key (Char, optional): SSH private key record reference.
                Defaults to None.
            configuration_variables (Dict, optional): Custom configuration variable.
                Following format is used:
                    `variable_reference`: `variable_value_char`
                    eg:
                    {'branch': 'prod', 'odoo_version': '16.0'}
            pick_all_template_variables (bool):  This parameter ensures that the server
                being created considers existing variables from the template.
                If enabled, the template variables will also be included in the server
                variables. The default value is True.

        Returns:
            cx.tower.server: newly created server record
        """
        self.ensure_one()

        # Retrieve the passed variables
        configuration_variables = kwargs.get("configuration_variables", {})

        # We validate mandatory variables
        if not kwargs.get("pick_all_template_variables"):
            self._validate_required_variables(configuration_variables)

        # We are using sudo to ensure all values are copied
        server_values = self.sudo()._prepare_server_values(
            name=name,
            server_template_id=self.id,  # pylint: disable=no-member
            **kwargs,
        )

        # Pop variable values to add them after server creation.
        # This is needed to ensure that access rules are applied properly.
        variable_values = server_values.pop("variable_value_ids")

        # Prepare context for server creation
        context = self.env.context.copy()

        # SSH setting may be added after server creation.
        context.update({"skip_ssh_settings_check": True})
        # We need to remove default_server_template_id to avoid it being used
        # in variable values.
        context.pop("default_server_template_id", None)

        # Create server
        server = (
            self.env["cx.tower.server"]  # pylint: disable=context-overridden # new need a new clean context
            .sudo()
            .with_context(context)
            .create(server_values)
            .sudo()
        )

        # Add variable values
        if variable_values:
            server.with_context(context).write({"variable_value_ids": variable_values})  # pylint: disable=context-overridden # new need a new clean context

        # Create server logs
        logs = server.server_log_ids.filtered(lambda rec: rec.log_type == "file")
        for log in logs.sudo():
            log.file_id = log.file_template_id.create_file(
                server=server, if_file_exists="skip"
            ).id

        flight_plan = server.server_template_id.flight_plan_id
        if flight_plan:
            server.run_flight_plan(flight_plan)

        return server

    def _get_post_create_fields(self):
        """
        Add fields that should be populated after server template creation
        """
        res = super()._get_post_create_fields()
        return res + ["variable_value_ids", "server_log_ids"]

    def _get_fields_tower_server(self):
        """
        Return field name list to read from template and create new server
        """
        return [
            "ssh_username",
            "ssh_password",
            "ssh_key_id",
            "ssh_auth_mode",
            "use_sudo",
            "color",
            "os_id",
            "plan_delete_id",
            "tag_ids",
            "variable_value_ids",
            "server_log_ids",
            "shortcut_ids",
            "scheduled_task_ids",
        ]

    def _prepare_server_values(self, pick_all_template_variables=True, **kwargs):
        """
        Prepare the server values to create a new server based on
        the current template. It reads all fields from the template, copies them,
        and processes One2many fields to create new related records. Magic fields
        like 'id', concurrency fields, and audit fields are excluded from the copied
        data.

        Args:
            pick_all_template_variables (bool):  This parameter ensures that the server
                being created considers existing variables from the template.
                If enabled, the template variables will also be included in the server
                variables. The default value is True.
            **kwargs: Additional values to update in the final server record.

        Returns:
            list: A list of dictionaries representing the values for the new server
                  records.
        """
        model_fields = self._fields
        field_o2m_type = fields.One2many

        # define the magic fields that should not be copied
        # (including ID)
        MAGIC_FIELDS = models.MAGIC_COLUMNS

        # read all values required to create a new server from the template
        values = self.read(self._get_fields_tower_server(), load=False)[0]

        # prepare server config values from kwargs
        server_config_values = self._parse_server_config_values(kwargs)
        template = self.browse(values["id"])

        # Process each field in the template
        for field in values.keys():
            if isinstance(model_fields[field], field_o2m_type):
                # get related records for One2many field
                related_records = getattr(template, field)
                new_records = []
                # for each related record, read its data and prepare it for copying
                for record in related_records:
                    record_data = {
                        k: v
                        for k, v in record.read(load=False)[0].items()
                        if k not in MAGIC_FIELDS
                    }
                    # set the inverse field (link back to the template)
                    # to False to unlink from the original template
                    record_data[model_fields[field].inverse_name] = False
                    new_records.append((0, 0, record_data))

                values[field] = new_records

        # Handle configuration variables if provided.
        configuration_variables = kwargs.pop("configuration_variables", None)
        configuration_variable_options = kwargs.pop(
            "configuration_variable_options", {}
        )

        if configuration_variables:
            # Validate required variables
            self._validate_required_variables(configuration_variables)

            # Search for existing variable options.
            option_references = list(configuration_variable_options.values())
            existing_options = option_references and self.env[
                "cx.tower.variable.option"
            ].search([("reference", "in", option_references)])
            missing_options = list(
                set(option_references)
                - {option.reference for option in existing_options}
            )

            if missing_options:
                # Map variable references to their corresponding
                # invalid option references.
                missing_options_to_variables = {
                    var_ref: opt_ref
                    for var_ref, opt_ref in configuration_variable_options.items()
                    if opt_ref in missing_options
                }
                # Generate a detailed error message for invalid variable options.
                detailed_message = "\n".join(
                    _(
                        "Variable reference '%(var_ref)s' has an invalid "
                        "option reference '%(opt_ref)s'.",
                        var_ref=var_ref,
                        opt_ref=opt_ref,
                    )
                    for var_ref, opt_ref in missing_options_to_variables.items()
                )
                raise ValidationError(
                    _(
                        "Some variable options are invalid:\n%(detailed_message)s",
                        detailed_message=detailed_message,
                    )
                )

            # Map variable options to their IDs.
            configuration_variable_options_dict = {
                option.variable_id.id: option for option in existing_options
            }

            variable_obj = self.env["cx.tower.variable"]
            variable_references = list(configuration_variables.keys())

            # Search for existing variables or create new ones if missing.
            exist_variables = variable_obj.search(
                [("reference", "in", variable_references)]
            )
            missing_references = list(
                set(variable_references)
                - {variable.reference for variable in exist_variables}
            )
            variable_vals_list = [
                {"name": reference} for reference in missing_references
            ]
            new_variables = variable_obj.create(variable_vals_list)
            all_variables = exist_variables | new_variables

            # Build a dictionary {variable: variable_value}.
            configuration_variable_dict = {
                variable: configuration_variables[variable.reference]
                for variable in all_variables
            }

            server_variable_vals_list = []
            for variable, variable_value in configuration_variable_dict.items():
                variable_option = configuration_variable_options_dict.get(variable.id)

                server_variable_vals_list.append(
                    (
                        0,
                        0,
                        {
                            "variable_id": variable.id,
                            "value_char": variable_option
                            and variable_option.value_char
                            or variable_value,
                            "option_id": variable_option and variable_option.id,
                        },
                    )
                )

            if pick_all_template_variables:
                # update or add variable values
                existing_variable_values = values.get("variable_value_ids", [])
                variable_id_to_index = {
                    cmd[2]["variable_id"]: idx
                    for idx, cmd in enumerate(existing_variable_values)
                    if cmd[0] == 0 and "variable_id" in cmd[2]
                }

                # Update exist variable options
                for exist_variable_id, index in variable_id_to_index.items():
                    option = configuration_variable_options_dict.get(exist_variable_id)
                    if not option:
                        continue
                    existing_variable_values[index][2].update(
                        {
                            "option_id": option.id,
                            "value_char": option.value_char,
                        }
                    )

                # Prepare new command values for server variables
                for new_command in server_variable_vals_list:
                    variable_id = new_command[2]["variable_id"]
                    if variable_id in variable_id_to_index:
                        idx = variable_id_to_index[variable_id]
                        # update exist command
                        existing_variable_values[idx] = new_command
                    else:
                        # add new command
                        existing_variable_values.append(new_command)

                values["variable_value_ids"] = existing_variable_values
            else:
                values["variable_value_ids"] = server_variable_vals_list

        # remove the `id` field to ensure a new record is created
        # instead of updating the existing one
        del values["id"]
        # update the values with additional arguments from kwargs
        values.update(kwargs)
        # update server configs
        values.update(server_config_values)
        # Add current user as user/manager to the newly created server
        values.update(
            {
                "user_ids": [(6, 0, self._default_user_ids())],
                "manager_ids": [(6, 0, self._default_manager_ids())],
            }
        )

        return values

    def _parse_server_config_values(self, config_values):
        """
        Prepares server configuration values.

        Args:
            config_values (dict): A dictionary containing server configuration values.
                Keys and their expected values:
                    - partner (res.partner, optional): The partner this server
                      belongs to.
                    - ipv4 (str, optional): IPv4 address. Defaults to None.
                    - ipv6 (str, optional): IPv6 address. Must be provided if IPv4 is
                      not specified. Defaults to None.
                    - ssh_key (str, optional): Reference to an SSH private key record.
                      Defaults to None.

        Returns:
            dict: A dictionary containing parsed server configuration values with the
                following keys:
                    - partner_id (int, optional): ID of the partner.
                    - ssh_key_id (int, optional): ID of the associated SSH key.
                    - ip_v4_address (str, optional): Parsed IPv4 address.
                    - ip_v6_address (str, optional): Parsed IPv6 address.
        """
        values = {}

        # This field is always populated from Server Template and
        # cannot be altered with function params.
        config_values.pop("plan_delete_id", None)

        partner = config_values.pop("partner", None)
        if partner:
            values["partner_id"] = partner.id

        ssh_key_reference = config_values.pop("ssh_key", None)
        if ssh_key_reference:
            ssh_key = self.env["cx.tower.key"].get_by_reference(ssh_key_reference)
            if ssh_key:
                values["ssh_key_id"] = ssh_key.id

        ipv4 = config_values.pop("ipv4", None)
        if ipv4:
            values["ip_v4_address"] = ipv4

        ipv6 = config_values.pop("ipv6", None)
        if ipv6:
            values["ip_v6_address"] = ipv6

        return values

    def _validate_required_variables(self, configuration_variables):
        """
        Validate that all required variables are present, not empty,
        and that no required variable is entirely missing from the configuration.

        Args:
            configuration_variables (dict): A dictionary of variable references
                                             and their values.

        Raises:
            ValidationError: If all required variables are
                            missing from the configuration,
                            or if any required variable is empty or missing.
        """
        required_variables = self.variable_value_ids.filtered("required")
        if not required_variables:
            return

        required_refs = [var.variable_reference for var in required_variables]
        config_refs = list(configuration_variables.keys())

        missing_variables = [ref for ref in required_refs if ref not in config_refs]
        empty_variables = [
            ref
            for ref in required_refs
            if ref in config_refs and not configuration_variables[ref]
        ]

        if not (missing_variables or empty_variables):
            return

        error_parts = [
            _("Please resolve the following issues with configuration variables:")
        ]

        if missing_variables:
            error_parts.append(
                _(
                    "  - Missing variables: %(variables)s",
                    variables=", ".join(missing_variables),
                )
            )

        if empty_variables:
            error_parts.append(
                _(
                    "  - Empty values for variables: %(variables)s",
                    variables=", ".join(empty_variables),
                )
            )

        raise ValidationError("\n".join(error_parts))

    def _get_dependent_model_relation_fields(self):
        """Check cx.tower.reference.mixin for the function documentation"""
        res = super()._get_dependent_model_relation_fields()
        return res + ["variable_value_ids"]
