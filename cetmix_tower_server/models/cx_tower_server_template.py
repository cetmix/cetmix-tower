# Copyright (C) 2024 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class CxTowerServerTemplate(models.Model):
    """Server Template. Used to simplify server creation"""

    _name = "cx.tower.server.template"
    _inherit = ["cx.tower.reference.mixin", "mail.thread", "mail.activity.mixin"]
    _description = "Cetmix Tower Server Template"

    active = fields.Boolean(default=True)

    # --- Connection
    ssh_port = fields.Char(string="SSH port", required=True, default="22")
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
        comodel_name="cx.tower.tag",
        relation="cx_tower_server_template_tag_rel",
        column1="server_template_id",
        column2="tag_id",
        string="Tags",
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

    # --- Flight Plan
    flight_plan_id = fields.Many2one(
        "cx.tower.plan",
        help="This flight plan will be run upon server creation",
        domain="[('server_ids', '=', False)]",
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

    def _compute_server_count(self):
        """
        Compute total server counts created from the templates
        """
        for template in self:
            template.server_count = len(template.server_ids)

    def action_create_server(self):
        """
        Returns wizard action to create new server
        """
        self.ensure_one()
        context = self.env.context.copy()
        context.update(
            {
                "default_server_template_id": self.id,
                "default_ssh_port": self.ssh_port,
                "default_ssh_username": self.ssh_username,
                "default_ssh_password": self.ssh_password,
                "default_ssh_key_id": self.ssh_key_id.id,
                "default_ssh_auth_mode": self.ssh_auth_mode,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Create Server"),
            "res_model": "cx.tower.server.template.create.wizard",
            "view_mode": "form",
            "view_type": "form",
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
                "domain": [("server_template_id", "=", self.id)],
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
            ssh_private_key_value (Char, optional): SSH private key content.
                Defaults to None.
            ssh_private_key_value (cx.tower.key(), optional): SSH private key record.
                Defaults to None.
            configuration_variables (Dict, optional): Custom configuration variable.
                Following format is used:
                    `variable_reference`: `variable_value_char`
                    eg:
                    {'branch': 'prod', 'odoo_version': '16.0'}

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
            ssh_private_key_value (Char, optional): SSH private key content.
                Defaults to None.
            ssh_private_key_value (cx.tower.key(), optional): SSH private key record.
                Defaults to None.
            configuration_variables (Dict, optional): Custom configuration variable.
                Following format is used:
                    `variable_reference`: `variable_value_char`
                    eg:
                    {'branch': 'prod', 'odoo_version': '16.0'}

        Returns:
            cx.tower.server: newly created server record
        """
        servers = self.env["cx.tower.server"].create(
            self._prepare_server_values(
                name=name, server_template_id=self.id, **kwargs
            ),
        )

        for server in servers:
            logs = server.server_log_ids.filtered(lambda rec: rec.log_type == "file")
            for log in logs:
                log.file_id = log.file_template_id.create_file(
                    server=server, raise_if_exists=False
                ).id

            flight_plan = server.server_template_id.flight_plan_id
            if flight_plan:
                flight_plan.execute(server)

        return servers

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
            "tag_ids",
            "variable_value_ids",
            "server_log_ids",
        ]

    def _prepare_server_values(self, **kwargs):
        """
        Prepare the server values to create a new server based on
        the current template. It reads all fields from the template, copies them,
        and processes One2many fields to create new related records. Magic fields
        like 'id', concurrency fields, and audit fields are excluded from the copied
        data.

        Args:
            **kwargs: Additional values to update in the final server record.

        Returns:
            list: A list of dictionaries representing the values for the new server
                  records.
        """

        model_fields = self._fields
        field_o2m_type = fields.One2many

        # define the magic fields that should not be copied
        # (including ID and concurrency fields)
        MAGIC_FIELDS = models.MAGIC_COLUMNS + [self.CONCURRENCY_CHECK_FIELD]

        # read all values required to create a new server from the template
        vals_list = self.read(self._get_fields_tower_server(), load=False)

        # process each template record
        for values in vals_list:
            template = self.browse(values["id"])

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

            # custom specific variable values
            configuration_variables = kwargs.pop("configuration_variables", None)
            if configuration_variables:
                variable_vals_list = []
                variable_obj = self.env["cx.tower.variable"]

                for (
                    variable_reference,
                    variable_value,
                ) in configuration_variables.items():
                    variable = variable_obj.search(
                        [("reference", "=", variable_reference)]
                    )
                    if not variable:
                        variable = variable_obj.create(
                            {
                                "name": variable_reference,
                            }
                        )

                    variable_vals_list.append(
                        (
                            0,
                            0,
                            {
                                "variable_id": variable.id,
                                "value_char": variable_value,
                            },
                        )
                    )

                values["variable_value_ids"] = variable_vals_list

            # remove the `id` field to ensure a new record is created
            # instead of updating the existing one
            del values["id"]
            # update the values with additional arguments from kwargs
            values.update(kwargs)

        return vals_list
