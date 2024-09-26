# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from pytz import timezone

from odoo import api, fields, models, tools
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare
from odoo.tools.safe_eval import wrap_module

requests = wrap_module(__import__("requests"), ["post", "get", "request"])
json = wrap_module(__import__("json"), ["dumps"])


DEFAULT_PYTHON_CODE = """# Available variables:
#  - user: Current Odoo User
#  - env: Odoo Environment on which the action is triggered
#  - server: server on which the command is run
#  - time, datetime, dateutil, timezone: useful Python libraries
#  - requests: Python 'requests' library. Available methods: 'post', 'get', 'request'
#  - json: Python 'json' library. Available methods: 'dumps'
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


class CxTowerCommand(models.Model):
    _name = "cx.tower.command"
    _inherit = [
        "cx.tower.template.mixin",
        "cx.tower.reference.mixin",
        "cx.tower.access.mixin",
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
        ]

    active = fields.Boolean(default=True)
    allow_parallel_run = fields.Boolean(
        help="If enabled command can be run on the same server "
        "while the same command is still running.\n"
        "Returns ANOTHER_COMMAND_RUNNING if execution is blocked"
    )
    interpreter_id = fields.Many2one(
        comodel_name="cx.tower.interpreter",
    )
    server_ids = fields.Many2many(
        comodel_name="cx.tower.server",
        relation="cx_tower_server_command_rel",
        column1="command_id",
        column2="server_id",
        string="Servers",
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

    @api.depends("action")
    def _compute_code(self):
        """
        Compute default code
        """
        for command in self:
            if command.action == "python_code" and not command.code:
                command.code = DEFAULT_PYTHON_CODE
            elif command.action == "ssh_command":
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
