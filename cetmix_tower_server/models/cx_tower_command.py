# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from types import SimpleNamespace

from dns import exception, resolver, reversename
from pytz import timezone

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError
from odoo.tools import ormcache_context
from odoo.tools.float_utils import float_compare
from odoo.tools.safe_eval import wrap_module

from .constants import DEFAULT_PYTHON_CODE, DEFAULT_PYTHON_CODE_HELP

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
tldextract = wrap_module(__import__("tldextract"), ["extract"])
dns_resolver = wrap_module(resolver, ["resolve", "query"])
dns_reversename = wrap_module(reversename, ["from_address", "to_address"])
dns_exception = wrap_module(exception, ["DNSException"])


dns = SimpleNamespace(
    resolver=dns_resolver,
    reversename=dns_reversename,
    exception=dns_exception,
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
        "cx.tower.tag.mixin",
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
        relation="cx_tower_command_tag_rel",
        column1="command_id",
        column2="tag_id",
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
    template_code = fields.Text(
        string="Template Code",
        related="file_template_id.code",
        readonly=True,
        help="Code of the associated file template",
    )
    flight_plan_line_ids = fields.One2many(
        comodel_name="cx.tower.plan.line",
        related="flight_plan_id.line_ids",
        readonly=True,
        help="Lines of the associated flight plan",
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
        copy=False,
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

    if_file_exists = fields.Selection(
        selection=[
            ("skip", "Skip"),
            ("overwrite", "Overwrite"),
            ("raise", "Raise Error"),
        ],
        default="skip",
        help="What to do if file already exists on the server.\n"
        "- Skip: Do not create or update the file.\n"
        "- Overwrite: Replace the existing file with the new one.\n"
        "- Raise Error: Raise an error if the file already exists.",
    )
    disconnect_file = fields.Boolean(
        string="Disconnect from Template",
        help=(
            "If enabled, disconnects the file from its template "
            "after running the command.\n"
        ),
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

    def _get_default_python_code_help(self):
        """
        Default python code help
        """

        # Available libraries are Odoo objects + Python libraries
        available_libraries = self._get_python_command_odoo_objects()
        available_libraries.update(self._get_python_command_libraries())
        help_text_fragments = []
        for key, value in available_libraries.items():
            help_text_fragments.append(f"<li><code>{key}</code>: {value['help']}</li>")

        help_text_fragments.append(
            f"<li><code>custom_values</code>: {_('Flight plan custom values')}</li>"
        )

        help_text = "<ul>" + "".join(help_text_fragments) + "</ul>"
        return f"{DEFAULT_PYTHON_CODE_HELP}{help_text}"

    # -- Computes
    @api.depends("action")
    def _compute_code(self):
        """
        Compute default code
        """
        default_python_code = self._get_default_python_code()
        for command in self:
            if command.action == "python_code":
                command.code = default_python_code
                continue
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
        Open current command log records
        """
        self.ensure_one()
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

    def _check_server_compatibility(self, server):
        """Check if the command is compatible with the server
        Args:
            server (cx.tower.server()): Server object

        Returns:
            bool: True if the command is compatible with the server, False otherwise
        """
        self.ensure_one()
        return not self.server_ids or server.id in self.server_ids.ids

    # -- Business logic
    @ormcache_context(keys=("lang",))
    @api.model
    def _get_python_command_libraries(self):
        """
        Get available python imports. Use this method to import python libraries.
        Please be advised, that this method is cached.
        If you need to use a non-cached import, eg for Odoo objects,
        use the `_get_python_command_odoo_objects` method instead.


        Returns:
            dict: Available libraries:
                {"<library_name>": {
                    "import": <library_import>,
                    "help": <library_help_html>
                }}
        """
        python_libraries = {
            "time": {
                "import": tools.safe_eval.time,
                "help": _("Python 'time' library"),
            },
            "datetime": {
                "import": tools.safe_eval.datetime,
                "help": _("Python 'datetime' library"),
            },
            "dateutil": {
                "import": tools.safe_eval.dateutil,
                "help": _("Python 'dateutil' library"),
            },
            "timezone": {
                "import": timezone,
                "help": _("Python 'timezone' library"),
            },
            "requests": {
                "import": requests,
                "help": _(
                    "Python 'requests' library. Available methods: 'post', 'get',"
                    " 'delete', 'request'"
                ),
            },
            "json": {
                "import": json,
                "help": _("Python 'json' library. Available methods: 'dumps'"),
            },
            "float_compare": {
                "import": float_compare,
                "help": _("Float compare. Odoo helper function to compare floats."),
            },
            "UserError": {
                "import": UserError,
                "help": _("UserError. Helper to raise UserError."),
            },
            "hashlib": {
                "import": hashlib,
                "help": _(
                    "Python 'hashlib' library. "
                    "<a href='https://docs.python.org/3/library/hashlib.html'"
                    " target='_blank'>Documentation</a>. "
                    "Available methods: 'sha1', 'sha224', "
                    "'sha256', 'sha384',"
                    " 'sha512', 'sha3_224', 'sha3_256', 'sha3_384', 'sha3_512', "
                    "'shake_128', 'shake_256',"
                    " 'blake2b', 'blake2s', 'md5', 'new'"
                ),
            },
            "hmac": {
                "import": hmac,
                "help": _(
                    "Python 'hmac' library. "
                    "<a href='https://docs.python.org/3/library/hmac.html'"
                    " target='_blank'>Documentation</a>. "
                    "Use 'new' to create HMAC objects. "
                    "Available methods on the HMAC *object*: 'update', 'copy',"
                    " 'digest', 'hexdigest'. "
                    " Module-level function: 'compare_digest'."
                ),
            },
            "tldextract": {
                "import": tldextract,
                "help": _(
                    "Python 'tldextract' library. Use "
                    "<code>tldextract.extract()</code> to parse domains. "
                    "Check <a href='https://github.com/john-kurkowski/tldextract'"
                    " target='_blank'>tldextract</a> for more information."
                ),
            },
            "dns": {
                "import": dns,
                "help": _(
                    "Python 'dnspython' library. "
                    "<a href='https://dnspython.readthedocs.io'"
                    " target='_blank'>Documentation</a>."
                    "<ul><li><code>dns.resolver</code>: "
                    "wrapped dnspython. Use "
                    '<code>dns.resolver.resolve(hostname, "A")</code> for '
                    "DNS lookups.</li>"
                    "<li><code>dns.reversename</code>: wrapped dnspython. "
                    'Use <code>dns.reversename.from_address("8.8.8.8")</code>'
                    " to build and reverse PTR records.</li>"
                    "<li><code>dns.exception</code>: wrapped dnspython. "
                    "Catch "
                    "<code>dns.exception.DNSException</code> to handle "
                    "DNS-related errors.</li>"
                    "</ul>"
                ),
            },
        }
        custom_python_libraries = self._custom_python_libraries()
        for libraries in custom_python_libraries.values():
            python_libraries.update(libraries)
        return python_libraries

    def _get_python_command_odoo_objects(self, server=None):
        """
        This method is used to import Odoo objects.
        Because Odoo objects can be records, this method is not cached.
        Use this method to import Odoo objects that are not cached.
        If you need to import some static objects, use the
        `_get_python_command_libraries` method instead.

        Args:
            server: Server to get the Odoo objects for.

        Returns:
            dict: Available Odoo objects:
                {"<object_name>": {
                    "import": <object_import>,
                    "help": <object_help_html>
                }}
        """
        return {
            "uid": {"import": self._uid, "help": _("Current Odoo user ID")},
            "user": {"import": self.env.user, "help": _("Current Odoo user")},
            "env": {"import": self.env, "help": _("Odoo Environment")},
            "server": {
                "import": server,
                "help": _("Current Cetmix Tower server this command is running on"),
            },
            "tower": {
                "import": self.env["cetmix.tower"],
                "help": _(
                    "Cetmix Tower "
                    "<a href='https://cetmix.com/tower/documentation/odoo_automation'"
                    " target='_blank'>helper class</a> shortcut"
                ),
            },
            "tower_servers": {
                "import": self.env["cx.tower.server"],
                "help": _("A helper shortcut to <code>env['cx.tower.server']</code>"),
            },
            "tower_commands": {
                "import": self.env["cx.tower.command"],
                "help": _("A helper shortcut to <code>env['cx.tower.command']</code>"),
            },
            "tower_plans": {
                "import": self.env["cx.tower.plan"],
                "help": _("A helper shortcut to <code>env['cx.tower.plan']</code>"),
            },
        }

    def _custom_python_libraries(self):
        """
        This function is designed to be used in custom modules
        extending Cetmix Tower to add  custom python libraries
        to the evaluation context.

        Returns:
            Dict: Custom python libraries.

        The following format is used:
        {
            <module_name>: {"<library_name>": {
                "import": <library_import>,
                "help": <library_help_html>
            }
        }

        Where:

        <module_name> Odoo module technical name.
        <library_name> is the name of the library how it will be used in the code.
        <library_import> is the library to import.
        <library_help_html> is the help text for the library shown in the "Help" tab.

        Example:

        ```python
        # Custom module extending Cetmix Tower
        custom_python_libraries = super()._custom_python_libraries()
        custom_python_libraries.update({
            "cetmix_tower_aws": {
                "boto3": {
                    "import": boto3,
                    "help": "Python 'boto3' library. "
                    "<a href='https://boto3.amazonaws.com/v1/documentation/api/latest/index.html'"
                    " target='_blank'>Documentation</a>."
                },
                "custom_library_name": {
                    "import": custom_library_import,
                    "help": "Custom library help text"
                }
            }
        })
        return custom_python_libraries

        ```
        """
        return {}

    def _get_python_command_eval_context(self, server=None, **kwargs):
        """
        Get the evaluation context for the python command.
        This method is used to get the evaluation context for the python command.

        Args:
            server: Server to get the evaluation context for.

        Returns:
            dict: Evaluation context for the python command.
        """

        # Get the Odoo objects first
        imports = self._get_python_command_odoo_objects(server=server)

        # Update with the libraries
        imports.update(self._get_python_command_libraries())
        eval_context = {key: value["import"] for key, value in imports.items()}

        eval_context["custom_values"] = kwargs.get("variable_values", {})
        return eval_context
