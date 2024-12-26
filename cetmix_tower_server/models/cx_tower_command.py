# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from pytz import timezone

from odoo import api, fields, models, tools
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare
from odoo.tools.safe_eval import wrap_module

requests = wrap_module(__import__("requests"), ["post", "get", "request"])
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

DEFAULT_PYTHON_CODE = """# Available variables:
#  - user: Current Odoo User
#  - env: Odoo Environment on which the action is triggered
#  - server: server on which the command is run
#  - tower: 'cetmix.tower' helper class
#  - time, datetime, dateutil, timezone: useful Python libraries
#  - requests: Python 'requests' library. Available methods: 'post', 'get', 'request'
#  - json: Python 'json' library. Available methods: 'dumps'
#  - hashlib: Python 'hashlib' library. Available methods: 'sha1', 'sha224', 'sha256',
#    'sha384', 'sha512', 'sha3_224', 'sha3_256', 'sha3_384', 'sha3_512', 'shake_128',
#    'shake_256', 'blake2b', 'blake2s', 'md5', 'new'
#  - hmac: Python 'hmac' library. Use 'new' to create HMAC objects.
#    Available methods on the HMAC *object*: 'update', 'copy', 'digest', 'hexdigest'.
#    Module-level function: 'compare_digest'.
#  - float_compare: Odoo function to compare floats based on specific precisions
#  - UserError: Warning Exception to use with raise
#
# Each python code command returns the COMMAND_RESULT value which is a dictionary.
# There are two default keys in the dictionary, e.g.:
# x = 2*10
# COMMAND_RESULT = {
#    "exit_code": x,
#    "message": "This will be logged as an error message because exit code !=0",
# }
\n\n\n"""

DEFAULT_SSH_CODE = """# Run any SSH command on the target system
# Examples: ls, cd, pwd, mkdir, rm
# Adapt commands to your specific OS.
\n\n\n"""


class CxTowerCommand(models.Model):
    _name = "cx.tower.command"
    _inherit = [
        "cx.tower.template.mixin",
        "cx.tower.reference.mixin",
        "cx.tower.access.mixin",
        "cx.tower.key.mixin",
    ]
    _description = "Cetmix Tower Command"
    _order = "name"

    def _selection_action(self):
        """Actions that can be run by a command.

        Returns:
            List of tuples: available options.
        """
        return [
            ("ssh_command", "SSH command"),
            ("python_code", "Execute Python code"),
            ("file_using_template", "Create file using template"),
            ("plan", "Run flight plan"),
        ]

    active = fields.Boolean(default=True)
    allow_parallel_run = fields.Boolean(
        help="If enabled command can be run on the same server "
        "while the same command is still running.\n"
        "Returns ANOTHER_COMMAND_RUNNING if execution is blocked"
    )
    server_ids = fields.Many2many(
        comodel_name="cx.tower.server",
        relation="cx_tower_server_command_rel",
        column1="command_id",
        column2="server_id",
        string="Servers",
        help="Servers on which the command will be executed.\n"
        "If empty, command canbe executed on all servers",
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
        help="Location where command will be executed. "
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
    flight_plan_id = fields.Many2one(
        comodel_name="cx.tower.plan",
    )
    server_status = fields.Selection(
        selection=lambda self: self.env["cx.tower.server"]._selection_status(),
        string="Server Status",
        help="Set the following status if command is executed successfully. "
        "Leave 'Undefined' if you don't need to update the status",
    )
    variable_ids = fields.Many2many(
        comodel_name="cx.tower.variable",
        relation="cx_tower_command_variable_rel",
        column1="command_id",
        column2="variable_id",
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
            - `code`: The command's script or execution logic.
            - `path`: The default execution path for the command.
        """
        return ["code", "path"]

    # Depend on related servers and partners
    @api.depends(
        "code",
        "server_ids",
        "server_ids.partner_id",
        "secret_ids.server_id",
        "secret_ids.partner_id",
    )
    def _compute_secret_ids(self):
        return super()._compute_secret_ids()

    @api.depends("action")
    def _compute_code(self):
        """
        Compute default code
        """
        for command in self:
            if command.action == "python_code":
                command.code = DEFAULT_PYTHON_CODE
            elif command.action == "ssh_command":
                command.code = DEFAULT_SSH_CODE
            else:
                command.code = False

    @api.model
    def _get_eval_context(self, server=None):
        """
        Evaluation context to pass to safe_eval to execute python code
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

    def name_get(self):
        # Add 'command_show_server_names' context key
        # to append server names to command
        if not self._context.get("command_show_server_names"):
            return super().name_get()
        res = []
        for rec in self:
            if rec.server_ids:
                name = "{} ({})".format(
                    rec.name, ",".join(rec.server_ids.mapped("name"))
                )
            else:
                name = rec.name
            res.append((rec.id, name))
        return res

    def action_open_command_logs(self):
        """
        Open current current command log records
        """
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_command_log"
        )
        action["domain"] = [("command_id", "=", self.id)]
        return action

    def _compose_secret_search_domain(self, key_refs):
        # Check server anb partner specific secrets
        return [
            ("reference", "in", key_refs),
            "|",
            "|",
            ("server_id", "in", self.server_ids.ids),
            ("partner_id", "in", self.server_ids.partner_id.ids),
            "&",
            ("server_id", "=", False),
            ("partner_id", "=", False),
        ]
