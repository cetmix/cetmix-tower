# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from pytz import timezone

from odoo import api, fields, models, tools
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare
from odoo.tools.safe_eval import wrap_module

from .constants import DEFAULT_PYTHON_CODE, DEFAULT_PYTHON_CODE_HELP, DEFAULT_SSH_CODE

requests = wrap_module(__import__("requests"), ["post", "get", "delete", "request"])
json = wrap_module(__import__("json"), ["dumps"])
hashlib = wrap_module(
    __import__("hashlib"),
    [
        "sha1",
        "sha224",
        "sha256",
        "sha384",
        "sha512",
        "sha3_224",
        "sha3_256",
        "sha3_384",
        "sha3_512",
        "shake_128",
        "shake_256",
        "blake2b",
        "blake2s",
        "md5",
        "new",
    ],
)
hmac = wrap_module(
    __import__("hmac"),
    ["new", "compare_digest"],
)


class CxTowerCommand(models.Model):
    """Command to run on a server"""

    _name = "cx.tower.command"
    _inherit = [
        "cx.tower.template.mixin",
        "cx.tower.reference.mixin",
        "cx.tower.access.mixin",
        "cx.tower.access.role.mixin",
        "cx.tower.key.mixin",
    ]
    _description = "Cetmix Tower Command"
    _order = "name"

    active = fields.Boolean(default=True)
    allow_parallel_run = fields.Boolean(
        help="If enabled, multiple instances of the same command "
        "can be run on the same server at the same time.\n"
        "Otherwise, ANOTHER_COMMAND_RUNNING status will be returned if another"
        " instance of the same command is already running"
    )
    server_ids = fields.Many2many(
        comodel_name="cx.tower.server",
        relation="cx_tower_server_command_rel",
        column1="command_id",
        column2="server_id",
        string="Servers",
        help="Servers on which the command will be run.\n"
        "If empty, command can be run on all servers",
    )
    tag_ids = fields.Many2many(
        comodel_name="cx.tower.tag",
        relation="cx_tower_command_tag_rel",
        column1="command_id",
        column2="tag_id",
        string="Tags",
    )
    os_ids = fields.Many2many(
        comodel_name="cx.tower.os",
        relation="cx_tower_os_command_rel",
        column1="command_id",
        column2="os_id",
        string="OSes",
    )
    note = fields.Text()

    action = fields.Selection(
        selection=lambda self: self._selection_action(),
        required=True,
        default=lambda self: self._selection_action()[0][0],
    )
    path = fields.Char(
        string="Default Path",
        help="Location where command will be run. "
        "You can use {{ variables }} in path",
    )
    file_template_id = fields.Many2one(
        comodel_name="cx.tower.file.template",
        help="This template will be used to create or update the pushed file",
    )
    code = fields.Text(
        compute="_compute_code",
        store=True,
        readonly=False,
    )
    command_help = fields.Html(
        compute="_compute_command_help",
        compute_sudo=True,
    )
    flight_plan_id = fields.Many2one(
        comodel_name="cx.tower.plan",
        help="Flight plan run by the command",
    )
    flight_plan_used_ids = fields.Many2many(
        comodel_name="cx.tower.plan",
        help="Flight plan this command is used in",
        relation="cx_tower_command_flight_plan_used_id_rel",
        column1="command_id",
        column2="plan_id",
        store=True,
    )
    flight_plan_used_ids_count = fields.Integer(
        compute="_compute_flight_plan_used_ids_count",
        help="Flight plan this command is used in",
    )
    server_status = fields.Selection(
        selection=lambda self: self.env["cx.tower.server"]._selection_status(),
        help="Set the following status if command finishes with success. "
        "Leave 'Undefined' if you don't need to update the status",
    )
    no_split_for_sudo = fields.Boolean(
        string="No Split for sudo",
        help="If enabled, do not split command on '&&' when using sudo."
        "Prepend sudo once to the whole command.",
    )
    variable_ids = fields.Many2many(
        comodel_name="cx.tower.variable",
        relation="cx_tower_command_variable_rel",
        column1="command_id",
        column2="variable_id",
    )

    # ---- Access. Add relation for mixin fields
    user_ids = fields.Many2many(
        relation="cx_tower_command_user_rel",
    )
    manager_ids = fields.Many2many(
        relation="cx_tower_command_manager_rel",
    )

    @classmethod
    def _get_depends_fields(cls):
        """
        Define dependent fields for computing `variable_ids` in command-related models.

        This implementation specifies that the fields `code` and `path`
        are used to determine the variables associated with a command.

        Returns:
            list: A list of field names (str) representing the dependencies.

        Example:
            The following fields trigger recomputation of `variable_ids`:
            - `code`: The command's script or running logic.
            - `path`: The default running path for the command.
        """
        return ["code", "path"]

    # -- Selection
    def _selection_action(self):
        """Actions that can be run by a command.

        Returns:
            List of tuples: available options.
        """
        return [
            ("ssh_command", "SSH command"),
            ("python_code", "Run Python code"),
            ("file_using_template", "Create file using template"),
            ("plan", "Run flight plan"),
        ]

    # -- Defaults
    def _get_default_python_code(self):
        """
        Default python command code
        """
        return DEFAULT_PYTHON_CODE

    def _get_default_ssh_code(self):
        """
        Default ssh command code
        """
        return DEFAULT_SSH_CODE

    def _get_default_python_code_help(self):
        """
        Default python code help
        """
        return DEFAULT_PYTHON_CODE_HELP

    # -- Computes
    @api.depends("action")
    def _compute_code(self):
        """
        Compute default code
        """
        default_python_code = self._get_default_python_code()
        default_ssh_code = self._get_default_ssh_code()
        for command in self:
            if command.action == "python_code":
                command.code = default_python_code
            elif command.action == "ssh_command":
                command.code = default_ssh_code
            else:
                command.code = False

    @api.depends("action")
    def _compute_command_help(self):
        """
        Compute command help
        """
        default_python_code_help = self._get_default_python_code_help()
        for command in self:
            if command.action == "python_code":
                command.command_help = default_python_code_help
            else:
                command.command_help = False

    @api.depends("flight_plan_used_ids")
    def _compute_flight_plan_used_ids_count(self):
        """
        Compute flight plan ids count
        """
        for command in self:
            command.flight_plan_used_ids_count = len(command.flight_plan_used_ids)

    def action_open_command_logs(self):
        """
        Open current current command log records
        """
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_command_log"
        )
        action["domain"] = [("command_id", "=", self.id)]
        return action

    def action_open_plans(self):
        """
        Open plans this command is used in
        """
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_plan"
        )
        action["domain"] = [("id", "in", self.flight_plan_used_ids.ids)]
        return action

    # -- Business logic
    @api.model
    def _get_eval_context(self, server=None):
        """
        Evaluation context to pass to safe_eval to run python code
        """
        return {
            "uid": self._uid,
            "user": self.env.user,
            "time": tools.safe_eval.time,
            "datetime": tools.safe_eval.datetime,
            "dateutil": tools.safe_eval.dateutil,
            "timezone": timezone,
            "requests": requests,
            "json": json,
            "float_compare": float_compare,
            "env": self.env,
            "UserError": UserError,
            "server": server or self._context.get("active_server"),
            "tower": self.env["cetmix.tower"],
            "hashlib": hashlib,
            "hmac": hmac,
        }
