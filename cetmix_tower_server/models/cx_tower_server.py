# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import ast
import io
import logging
from datetime import timedelta
from functools import wraps

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

from odoo.addons.base.models.res_users import check_identity

from ..ssh.ssh import SSHConnection, SSHManager
from .constants import (
    ANOTHER_COMMAND_RUNNING,
    COMMAND_NOT_COMPATIBLE_WITH_SERVER,
    COMMAND_TIMED_OUT,
    COMMAND_TIMED_OUT_MESSAGE,
    FILE_CREATION_FAILED,
    GENERAL_ERROR,
    NO_COMMAND_RUNNER_FOUND,
    PYTHON_COMMAND_ERROR,
    SSH_CONNECTION_ERROR,
)
from .tools import generate_random_id

_logger = logging.getLogger(__name__)


def ensure_ssh_disconnect(func):
    """
    Decorator that ensures the SSH connection is disconnected after the transaction
    completes, whether by commit or rollback.

    This decorator registers hooks (postcommit and postrollback) before calling the
    decorated function. Thus, even if the function raises an exception (and it's caught
    at a higher level), the hooks will still be executed, ensuring that the
    SSH connection is closed.
    """

    @wraps(func)
    def wrapped(self, *args, **kwargs):
        # Try to obtain the SSH connection once
        try:
            connection = self._get_ssh_client(raise_on_error=True)
        except Exception as e:
            _logger.error("Error obtaining SSH connection: %s", e)
            connection = None

        # Define a hook to disconnect the SSH connection using the obtained connection.
        def disconnect_connection():
            if connection:
                try:
                    connection.disconnect()
                except Exception as e:
                    _logger.error("Error disconnecting SSH connection: %s", e)

        # Register the disconnect hook for both commit and rollback events.
        self.env.cr.postcommit.add(disconnect_connection)
        self.env.cr.postrollback.add(disconnect_connection)

        # Call the decorated function.
        result = func(self, *args, **kwargs)
        return result

    return wrapped


class CxTowerServer(models.Model):
    """Represents a server entity

    Keeps information required to connect and perform routine operations
    such as configuration, file management etc"

    """

    _name = "cx.tower.server"
    _inherit = [
        "cx.tower.access.role.mixin",
        "cx.tower.variable.mixin",
        "cx.tower.reference.mixin",
        "mail.thread",
        "mail.activity.mixin",
        "cx.tower.vault.mixin",
        "cx.tower.tag.mixin",
    ]
    _description = "Cetmix Tower Server"
    _order = "name asc"

    SECRET_FIELDS = ["ssh_password", "host_key"]

    # ---- Main
    active = fields.Boolean(default=True)
    color = fields.Integer(help="For better visualization in views")
    partner_id = fields.Many2one(comodel_name="res.partner")
    status = fields.Selection(
        selection=lambda self: self._selection_status(),
        default=None,
        required=False,
    )

    # ---- Connection
    ip_v4_address = fields.Char(
        string="IPv4 Address", groups="cetmix_tower_server.group_manager"
    )
    ip_v6_address = fields.Char(
        string="IPv6 Address", groups="cetmix_tower_server.group_manager"
    )
    skip_host_key = fields.Boolean(
        default=False,
        help="Enable to skip host key verification",
    )
    host_key = fields.Char(
        groups="cetmix_tower_server.group_manager",
        help="Host key to verify the server",
    )
    ssh_port = fields.Integer(
        string="SSH port",
        required=True,
        default=22,
        groups="cetmix_tower_server.group_manager",
    )
    ssh_username = fields.Char(
        string="SSH Username", required=True, groups="cetmix_tower_server.group_manager"
    )
    ssh_password = fields.Char(
        string="SSH Password",
        groups="cetmix_tower_server.group_manager",
    )
    ssh_key_id = fields.Many2one(
        comodel_name="cx.tower.key",
        string="SSH Private Key",
        domain=[("key_type", "=", "k")],
        groups="cetmix_tower_server.group_manager",
    )
    ssh_auth_mode = fields.Selection(
        string="SSH Auth Mode",
        selection=[
            ("p", "Password"),
            ("k", "Key"),
        ],
        default="p",
        required=True,
        groups="cetmix_tower_server.group_manager",
    )
    use_sudo = fields.Selection(
        string="Use sudo",
        selection=[("n", "Without password"), ("p", "With password")],
        help="Run commands using 'sudo'. Leave empty if 'sudo' is not needed.",
        groups="cetmix_tower_server.group_manager",
    )
    url = fields.Char(
        string="URL", help="Server web interface, eg 'https://doge.example.com'"
    )
    # ---- Variables
    variable_value_ids = fields.One2many(
        inverse_name="server_id"  # Other field properties are defined in mixin
    )

    # ---- Keys
    secret_ids = fields.One2many(
        string="Secrets",
        comodel_name="cx.tower.key.value",
        inverse_name="server_id",
        groups="cetmix_tower_server.group_manager",
    )

    # ---- Attributes
    os_id = fields.Many2one(
        string="Operating System",
        comodel_name="cx.tower.os",
        groups="cetmix_tower_server.group_manager",
    )
    tag_ids = fields.Many2many(
        relation="cx_tower_server_tag_rel",
        column1="server_id",
        column2="tag_id",
    )
    note = fields.Text()
    command_log_ids = fields.One2many(
        comodel_name="cx.tower.command.log", inverse_name="server_id"
    )
    plan_log_ids = fields.One2many(
        comodel_name="cx.tower.plan.log", inverse_name="server_id"
    )
    file_ids = fields.One2many(
        "cx.tower.file",
        "server_id",
        string="Files",
    )
    file_count = fields.Integer(
        "Total Files",
        compute="_compute_file_count",
    )

    # ---- Server logs
    server_log_ids = fields.One2many(
        string="Server Logs",
        comodel_name="cx.tower.server.log",
        inverse_name="server_id",
    )

    # ---- Related server template
    server_template_id = fields.Many2one(
        "cx.tower.server.template",
        readonly=True,
        index=True,
    )

    # ---- Delete plan
    plan_delete_id = fields.Many2one(
        "cx.tower.plan",
        string="On Delete Plan",
        groups="cetmix_tower_server.group_manager",
        help="This Flightplan will be run when the server is deleted",
    )

    # ---- Access. Add relation for mixin fields

    user_ids = fields.Many2many(
        relation="cx_tower_server_user_rel",
    )
    manager_ids = fields.Many2many(
        relation="cx_tower_server_manager_rel",
    )

    # ---- Shortcuts
    shortcut_ids = fields.Many2many(
        comodel_name="cx.tower.shortcut",
        relation="cx_tower_server_shortcut_rel",
        column1="server_id",
        column2="shortcut_id",
        string="Shortcuts",
    )

    # ---- Scheduled Tasks
    scheduled_task_ids = fields.Many2many(
        comodel_name="cx.tower.scheduled.task",
        relation="cx_tower_scheduled_task_server_rel",
        column1="server_id",
        column2="scheduled_task_id",
        string="Scheduled Tasks",
    )

    command_ids = fields.Many2many(
        comodel_name="cx.tower.command",
        relation="cx_tower_server_command_rel",
        column1="server_id",
        column2="command_id",
        string="Commands",
    )

    plan_ids = fields.Many2many(
        comodel_name="cx.tower.plan",
        relation="cx_tower_plan_cx_tower_server_rel",
        column1="cx_tower_server_id",
        column2="cx_tower_plan_id",
        string="Flight Plans",
    )

    def _selection_status(self):
        """
        Status selection options

        Returns:
            list: status selection options
        """
        return [
            ("stopped", "Stopped"),
            ("starting", "Starting"),
            ("running", "Running"),
            ("stopping", "Stopping"),
            ("restarting", "Restarting"),
            ("deleting", "Deleting"),
            ("delete_error", "Deletion Error"),
        ]

    def _compute_file_count(self):
        """Compute total server files"""
        for server in self:
            server.file_count = len(server.file_ids)

    @api.constrains("ip_v4_address", "ip_v6_address", "ssh_auth_mode")
    def _constraint_ssh_settings(self):
        """Ensure SSH settings are valid.
        Set 'skip_ssh_settings_check' context key to skip the checks
        """
        # Skip the check if context key is set
        if self._context.get("skip_ssh_settings_check"):
            return

        for rec in self:
            # Combine all errors together
            validation_errors = []
            if not rec.ip_v4_address and not rec.ip_v6_address:
                validation_errors.append(
                    _(
                        "Please provide IPv4 or IPv6 address for %(srv)s",
                        srv=rec.name,
                    )
                )
            if rec.ssh_auth_mode == "k" and not rec.ssh_key_id:
                validation_errors.append(
                    _("Please provide SSH Key for %(srv)s", srv=rec.name)
                )

            # Raise errors if any
            if validation_errors:
                validation_error = "\n".join(validation_errors)
                raise ValidationError(validation_error)

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to validate SSH password before record creation."""
        # Validate SSH password before creating records
        if not self._context.get("skip_ssh_settings_check"):
            validation_errors = []
            for vals in vals_list:
                if vals.get("ssh_auth_mode") == "p" and not vals.get("ssh_password"):
                    server_name = vals["name"]
                    validation_errors.append(
                        _("Please provide SSH password for %(srv)s", srv=server_name)
                    )

            if validation_errors:
                raise ValidationError("\n".join(validation_errors))

        return super().create(vals_list)

    def unlink(self):
        """Run post-delete flight plan"""
        servers_to_delete = self.env["cx.tower.server"]
        flight_plan_log_obj = self.env["cx.tower.plan.log"]

        for server in self:
            # If forced, no delete plan, or already in deleting state,
            # skip plan running
            if (
                self._context.get("server_force_delete")
                or not server.plan_delete_id
                or server._is_being_deleted()
            ):
                servers_to_delete |= server
                continue

            plan_label = generate_random_id(4)
            server.plan_delete_id._run_single(server, plan_log={"label": plan_label})
            plan_log = flight_plan_log_obj.search(
                [
                    ("server_id", "=", server.id),
                    ("plan_id", "=", server.plan_delete_id.id),
                    ("label", "=", plan_label),
                ]
            )

            # If plan has finished, either mark for deletion or set an error
            if plan_log and plan_log.finish_date:
                if plan_log.plan_status == 0:
                    servers_to_delete |= server
                else:
                    server.status = "delete_error"
            else:
                # Plan still in progress
                server.status = "deleting"

        return super(CxTowerServer, servers_to_delete).unlink()

    @api.returns("self", lambda value: value.id)
    def copy(self, default=None):
        default = default or {}
        default["status"] = None

        file_ids = self.env["cx.tower.file"]
        for file in self.file_ids:
            file_ids |= file.copy(
                {
                    "auto_sync": False,
                    "keep_when_deleted": True,
                }
            )
        default["file_ids"] = file_ids.ids

        # Copy SSH password and host key
        default["ssh_password"] = self._get_secret_value("ssh_password")
        default["host_key"] = self._get_secret_value("host_key")
        result = super().copy(default=default)

        # Copy server secrets
        for secret in self.secret_ids:
            secret.sudo().copy({"server_id": result.id})

        for var_value in self.variable_value_ids:
            # Duplicating a server with variable values and then duplicating the
            # duplicate causes a uniqueness constraint error for the 'reference' field
            # in 'cx.tower.variable.value'. This happens because 'reference' is
            # generated from the 'name' field, which is a related field  fetching the
            # same value across duplications. To avoid this, we pass the existing
            # 'reference' as 'name' during duplication, ensuring unique 'reference'
            # generation for each copy.
            var_value.copy({"server_id": result.id, "name": var_value.reference})

        for server_log in self.server_log_ids:
            server_log.copy({"server_id": result.id})

        return result

    # ------------------------------
    # ---- Actions
    # ------------------------------

    @check_identity
    def action_show_host_key(self):
        """Show host key"""
        self.ensure_one()
        try:
            host_key = self._get_host_key_from_host()
            is_error = False
        except Exception as error:
            is_error = True
            host_key = error
        context = {
            "default_host_key": host_key,
            "default_is_error": is_error,
            "default_server_id": self.id,
        }
        return {
            "type": "ir.actions.act_window",
            "name": _("Host Key"),
            "res_model": "cx.tower.server.host.key.wizard",
            "view_mode": "form",
            "target": "new",
            "context": context,
        }

    def action_update_server_logs(self):
        """Update selected log from its source."""
        for server in self:
            if server.server_log_ids:
                server.server_log_ids.action_update_log()

    def action_open_command_logs(self):
        """
        Open current server command log records
        """
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_command_log"
        )
        action["domain"] = [("server_id", "=", self.id)]  # pylint: disable=no-member
        return action

    def action_open_plan_logs(self):
        """
        Open current server flightplan log records
        """
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_plan_log"
        )
        action["domain"] = [("server_id", "=", self.id)]  # pylint: disable=no-member
        return action

    def action_run_command(self):
        """
        Returns wizard action to select command and run it
        """
        context = self.env.context.copy()
        context.update(
            {
                "default_server_ids": self.ids,
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

    def action_run_flight_plan(self):
        """
        Returns wizard action to select flightplan and run it
        """
        context = self.env.context.copy()
        context.update(
            {
                "default_server_ids": self.ids,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Run Flight Plan"),
            "res_model": "cx.tower.plan.run.wizard",
            "view_mode": "form",
            "target": "new",
            "context": context,
        }

    def action_open_files(self):
        """
        Open files of the current server
        """
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.cx_tower_file_action"
        )
        action["domain"] = [("server_id", "=", self.id)]  # pylint: disable=no-member

        context = self._context.copy()
        if "context" in action and isinstance((action["context"]), str):
            context.update(ast.literal_eval(action["context"]))
        else:
            context.update(action.get("context", {}))

        context.update(
            {
                "default_server_id": self.id,  # pylint: disable=no-member
            }
        )
        action["context"] = context
        return action

    # ------------------------------
    # ---- Connectivity
    # ------------------------------

    def _get_ssh_client(self, raise_on_error=False, timeout=5000, skip_host_key=False):
        """Create a new SSH client instance

        Args:
            raise_on_error (bool, optional): If true will raise exception
             in case or error, otherwise False will be returned
            Defaults to True.
            timeout (int, optional): SSH connection timeout in seconds.
            skip_host_key (bool, optional): If true will skip host key verification.
                Defaults to False.

        Raises:
            ValidationError: If the provided server reference is invalid or
                the server cannot be found.

        Returns:
            SSH: SSH manager instance or False and exception content
        """
        self.ensure_one()
        self = self.sudo()
        try:
            host_key = self._get_secret_value("host_key")

            # Check host only if IP address is present
            skip_host_key = skip_host_key or self.skip_host_key
            if (
                not host_key
                and not skip_host_key
                and (self.ip_v4_address or self.ip_v6_address)
            ):
                raise ValidationError(
                    _("Host key not found for server %(server)s", server=self.name)
                )

            connection = SSHConnection(
                host=self.ip_v4_address or self.ip_v6_address,
                port=self.ssh_port,
                username=self.ssh_username,
                password=self._get_ssh_password(),
                ssh_key=self._get_ssh_key(),
                host_key=host_key if host_key and not self.skip_host_key else None,
                mode=self.ssh_auth_mode,
                timeout=timeout,
            )
            client = SSHManager(connection)

        except Exception as e:
            if raise_on_error:
                raise ValidationError(_("SSH connection error %(err)s", err=e)) from e
            return False, e
        return client

    def test_ssh_connection(
        self,
        raise_on_error=True,
        return_notification=True,
        try_command=True,
        try_file=True,
        timeout=60,
    ):
        """Test SSH connection.

        Args:
            raise_on_error (bool, optional): Raise exception in case of error.
                Defaults to True.
            return_notification (bool, optional): Show sticky notification
                Defaults to True.
            try_command (bool, optional): Try to run a command.
                Defaults to True.
            try_file (bool, optional): Try file operations.
                Defaults to True.
            timeout (int, optional): SSH connection timeout in seconds.
                Defaults to 60.

        Raises:
            ValidationError: In case of SSH connection error.
            ValidationError: In case of no output received.
            ValidationError: In case of file operations error.

        Returns:
            dict: {
                "status": int,
                "response": str,
                "error": str,
            }
        """
        self.ensure_one()
        client = self._get_ssh_client(raise_on_error=raise_on_error, timeout=timeout)

        if not try_command and not try_file:
            try:
                client.connection.connect()
                return {
                    "status": 0,
                    "response": _("Connection successful."),
                    "error": "",
                }
            except Exception as e:
                if raise_on_error:
                    raise ValidationError(
                        _("SSH connection error %(err)s", err=e)
                    ) from e
                return {
                    "status": SSH_CONNECTION_ERROR,
                    "response": _("Connection failed."),
                    "error": e,
                }

        # Initialize test_result to None - will be set by try_command or try_file
        test_result = None

        # Try command
        if try_command:
            command = self._get_connection_test_command()
            test_result = self._run_command_using_ssh(
                client, command_code=command, **{"raise_on_error": raise_on_error}
            )
            status = test_result.get("status", 0)
            response = test_result.get("response") or ""
            error = test_result.get("error") or ""

            # Got an error
            if raise_on_error and (status != 0 or error):
                raise ValidationError(
                    _(
                        "Cannot run command\n. CODE: %(status)s. "
                        "RESULT: %(res)s. ERROR: %(err)s",
                        status=status,
                        res=response,
                        err=error,
                    )
                )

            # No output received
            if raise_on_error and not response:
                raise ValidationError(
                    _(
                        "No output received."
                        " Please log in manually and check for any issues.\n"
                        "===\nCODE: %(status)s",
                        status=status,
                    )
                )

        if try_file:
            # test upload file
            self.upload_file("test", "/tmp/cetmix_tower_test_connection.txt")

            # test download loaded file
            self.download_file("/tmp/cetmix_tower_test_connection.txt")

            # remove file from server
            file_test_result = self._run_command_using_ssh(
                client, command_code="rm -rf /tmp/cetmix_tower_test_connection.txt"
            )
            file_status = file_test_result.get("status", 0)
            file_error = file_test_result.get("error") or ""

            # In case of an error, raise or replace command result with file test result
            if file_status != 0 or file_error:
                if raise_on_error:
                    raise ValidationError(
                        _(
                            "Cannot remove test file using command.\n "
                            "CODE: %(status)s. ERROR: %(err)s",
                            err=file_error,
                            status=file_status,
                        )
                    )

            # Replace command result with file test result
            test_result = file_test_result

        # Return notification
        if return_notification:
            # Ensure test_result is set before accessing it
            if test_result is None:
                # Fallback: create a default success result
                test_result = {
                    "status": 0,
                    "response": _("Connection test passed."),
                    "error": "",
                }
            response = test_result.get("response") or ""
            return self._get_notification_action(
                _(
                    "Connection test passed! \n%(res)s",
                    res=response.rstrip(),
                ),
                notification_type="info",
                title=_("Success"),
                sticky=False,
            )

        # Ensure test_result is set before returning
        if test_result is None:
            # Fallback: create a default success result
            test_result = {
                "status": 0,
                "response": _("Connection test passed."),
                "error": "",
            }

        return test_result

    def _get_connection_test_command(self):
        """Get command used to test SSH connection

        Returns:
            Char: SSH command
        """
        command = "uname -a"
        return command

    def _get_ssh_password(self):
        """Get ssh password
        This function prepares and returns ssh password for the ssh connection
        Override this function to implement own password algorithms

        Returns:
            Char: password ready to be used for connection parameters
        """
        self.ensure_one()
        password = self._get_secret_value("ssh_password")
        return password

    def _get_ssh_key(self):
        """Get SSH key
        Get private key for an SSH connection

        Returns:
            Char: SSH private key
        """
        self.ensure_one()
        # To ensure that key will be read
        # regardless of access rights
        if self.sudo().ssh_key_id:
            # Use context key to read secret value
            ssh_key = self.ssh_key_id._get_secret_value("secret_value")
        else:
            ssh_key = None
        return ssh_key

    @ensure_ssh_disconnect
    def _get_host_key_from_host(self, raise_on_error=False, timeout=60):
        """Get host key

        Args:
            raise_on_error (bool, optional): If true will raise exception
            in case or error, otherwise False will be returned
            Defaults to True.
            timeout (int, optional): SSH connection timeout in seconds.

        Raises:
            ValidationError: If the provided server reference is invalid or
                the server cannot be found.

        Returns:
            Host key: Host key of the server
        """
        self.ensure_one()

        # Check access before getting host key
        # This is needed to avoid possible access violations
        self.check_access("read")

        try:
            # Skip host key verification to obtain the server's real host key.
            client = self._get_ssh_client(
                raise_on_error=raise_on_error, timeout=timeout, skip_host_key=True
            )

            # Disable host key verification for this connection only, to obtain the
            # server's real host key. If a pre-configured host key is incorrect using
            # it would cause a key mismatch error. By setting host_key to False
            # here, we trigger AutoAddPolicy for this connection, which automatically
            # accepts the server's actual host key.
            client.connection.host_key = False

            ssh_client = client.connection.connect()
            transport = ssh_client.get_transport()
            remote_key = transport.get_remote_server_key()
            host_key = remote_key.get_base64()
            return host_key
        except Exception as e:
            if raise_on_error:
                raise ValidationError(
                    _("Error retrieving host key: %(err)s", err=e)
                ) from e

    # ------------------------------
    # ---- Command execution
    # ------------------------------

    def run_command(self, command, path=None, sudo=None, ssh_connection=None, **kwargs):
        """This is the main function to use for running commands.
        It renders command code, creates log record and calls command runner.

        Args:
            command (cx.tower.command()): Command record
            path (Char): directory where command is run.
                Provide in case you need to override default command value
            sudo (Boolean): use sudo
                Defaults to None
            ssh_connection (SSH client instance, optional): SSH connection.
                Pass to reuse existing connection.
                This is useful in case you would like to speed up
                the ssh command running.
            kwargs (dict):  extra arguments. Use to pass external values.
                Following keys are supported by default:
                    - "log", dict(): values passed to logger
                    - "key", dict(): values passed to key parser
                    - "variable_values", dict(): custom variable values
                        in the format of `{variable_reference: variable_value}`
                        eg `{'odoo_version': '16.0'}`
                        Will be applied only if user has write access to the server.
        Context:
            no_command_log (Bool): set this context key to `True`
                to disable log creation.
            Command running results will be returned instead.
            If any non command related error occurs in the command running flow
            an exception will be raised.
            IMPORTANT: be aware when running commands with `no_command_log=True`
            because no `Allow Parallel Run` check will be done!
        Returns:
            dict(): command running result if `no_command_log`
                context value == True else None
        """
        self.ensure_one()

        # Populate `sudo` value from the server settings if not provided explicitly
        if self.sudo().ssh_username == "root":
            sudo = False
        elif sudo is None or sudo:
            sudo = self.sudo().use_sudo

        # Prepare log object
        log_obj = self.env["cx.tower.command.log"]
        log_vals = kwargs.get("log", {})
        log_vals.update(
            {"use_sudo": sudo, "variable_values": kwargs.get("variable_values", {})}
        )

        # Check if no log record should be created
        no_command_log = self._context.get("no_command_log")

        # Check if command can be run on this server:
        # 1. Server is listed in command's server_ids
        # 2. There are no server_ids at all (command is not server specific)
        if not command._check_server_compatibility(self):
            error = _("Command is not compatible with the server")
            if no_command_log:
                return {
                    "status": COMMAND_NOT_COMPATIBLE_WITH_SERVER,
                    "response": None,
                    "error": error,
                }
            log_obj.record(
                server_id=self.id,  # pylint: disable=no-member
                command_id=command.id,
                status=COMMAND_NOT_COMPATIBLE_WITH_SERVER,
                error=error,
                **log_vals,
            )
            return

        # Check if another instance of the same command is running
        another_command_running = (
            not command.allow_parallel_run
            and log_obj.sudo().search_count(
                [
                    ("server_id", "=", self.id),  # pylint: disable=no-member
                    ("command_id", "=", command.id),
                    ("is_running", "=", True),
                ]
            )
        )

        # Another command is running, return error
        if another_command_running:
            if no_command_log:
                return {
                    "status": ANOTHER_COMMAND_RUNNING,
                    "response": None,
                    "error": _("Another instance of the command is already running"),
                }
            log_obj.record(
                server_id=self.id,  # pylint: disable=no-member
                command_id=command.id,
                status=ANOTHER_COMMAND_RUNNING,
                error=_("Another instance of the command is already running"),
                **log_vals,
            )
            return

        # Render command
        custom_variable_values = kwargs.get("variable_values", {})
        rendered_command = self._render_command(command, path, custom_variable_values)
        rendered_command_code = rendered_command["rendered_code"]
        rendered_command_path = rendered_command["rendered_path"]

        # Prepare key renderer values
        key_vals = kwargs.get("key", {})  # Get vals from kwargs
        key_vals.update({"server_id": self.id})  # pylint: disable=no-member
        if self.partner_id:
            key_vals.update({"partner_id": self.partner_id.id})
        kwargs.update({"key": key_vals})

        # Save rendered code to log
        if no_command_log:
            log_record = None
        else:
            log_vals.update(
                {"code": rendered_command_code, "path": rendered_command_path}
            )
            # Create log record
            log_record = log_obj.start(self.id, command.id, **log_vals)  # pylint: disable=no-member
        # If on command we have the flag
        if command.no_split_for_sudo:
            kwargs["no_split_for_sudo"] = True
        return self._command_runner_wrapper(
            command=command,
            log_record=log_record,
            rendered_command_code=rendered_command_code,
            sudo=sudo,
            rendered_command_path=rendered_command_path,
            ssh_connection=ssh_connection,
            **kwargs,
        )

    def _render_command(self, command, path=None, custom_variable_values=None):
        """Renders command code for selected command for current server

        Args:
            command (cx.tower.command): Command to render
            path (Char): Path where to run the command.
                Provide in case you need to override default command path

        Returns:
            dict: rendered values
                {
                    "rendered_code": rendered command code,
                    "rendered_path": rendered command path
                }
        """
        self.ensure_one()

        variables = []

        # Get variables from code
        if command.code:
            variables_extracted = command.get_variables_from_code(command.code)
            for ve in variables_extracted:
                if ve not in variables:
                    variables.append(ve)

        # Get variables from path
        path = path if path else command.path
        if path:
            variables_extracted = command.get_variables_from_code(path)
            for ve in variables_extracted:
                if ve not in variables:
                    variables.append(ve)

        # Get variable values for current server
        variable_values_dict = (
            self.sudo().get_variable_values(variables)  # pylint: disable=no-member
            if variables
            else False
        )

        # Extract variable values for current server
        variable_values = (
            variable_values_dict.get(self.id) if variable_values_dict else {}
        )  # pylint: disable=no-member

        # Apply custom variable values only if user has write access to the server
        has_write_access = self._have_access_to_server("write")
        if custom_variable_values and has_write_access:
            variable_values.update(custom_variable_values)

        # Render command code and path using variables
        if variable_values:
            if command.action == "python_code":
                variable_values["pythonic_mode"] = True

            rendered_code = (
                command.render_code_custom(command.code, **variable_values)
                if command.code
                else False
            )
            rendered_path = (
                command.render_code_custom(path, **variable_values) if path else False
            )

        else:
            rendered_code = command.code
            rendered_path = path

        return {"rendered_code": rendered_code, "rendered_path": rendered_path}

    def _have_access_to_server(self, operation):
        """Check access to the server.
        This is a wrapper function over the Odoo built-in ones.
        It's used in order we need to implement custom access checks.

        Args:
            operation (Char): Operation to check access
                same format as `check_access_rights`
        Returns:
            Bool: True if access is granted, False otherwise
        """
        # Check access rights first
        return self.has_access(operation)

    def run_flight_plan(self, flight_plan, **kwargs):
        """
        Runs flight plan on the current server.

        Args:
            flight_plan (cx.tower.plan()): flight plan record
            kwargs (dict): Optional arguments
                Following are supported but not limited to:
                    - "plan_log": {values passed to flightplan logger}
                    - "log": {values passed to logger}
                    - "key": {values passed to key parser}
                    - "variable_values", dict(): custom variable values
                        in the format of `{variable_reference: variable_value}`
                        eg `{'odoo_version': '16.0'}`
                        Will be applied only if user has write access to the server.
        """

        self.ensure_one()

        # Run flight plan
        return flight_plan._run_single(self, **kwargs)

    def _command_runner_wrapper(
        self,
        command,
        log_record,
        rendered_command_code,
        sudo=None,
        rendered_command_path=None,
        ssh_connection=None,
        **kwargs,
    ):
        """Used to implement custom runner mechanisms.
        Use it in case you need to redefine the entire command running engine.
        Eg it's used in `cetmix_tower_server_queue` OCA `queue_job` implementation.

        Args:
            command (cx.tower.command()): Command
            log_record (cx.tower.command.log()): Command log record
            rendered_command_code (Text): Rendered command code.
                We are passing in case it differs from command code in the log record.
            sudo (Selection): Command sudo mode. Defaults to None.
            rendered_command_path (Char, optional): Rendered command path.
            ssh_connection (SSH client instance, optional): SSH connection to reuse.
        kwargs (dict):  extra arguments. Use to pass external values.
                Following keys are supported by default:
                    - "log": {values passed to logger}
                    - "key": {values passed to key parser}

        Context:
            use_sudo (Bool): use sudo for command running

        Returns:
            dict(): command running result if `log_record` is defined else None
        """
        return self._command_runner(
            command=command,
            log_record=log_record,
            rendered_command_code=rendered_command_code,
            sudo=sudo,
            rendered_command_path=rendered_command_path,
            ssh_connection=ssh_connection,
            **kwargs,
        )

    def _command_runner(
        self,
        command,
        log_record,
        rendered_command_code,
        sudo=None,
        rendered_command_path=None,
        ssh_connection=None,
        **kwargs,
    ):
        """Top level command runner function.
        Calls command type specific runners.

        Args:
            command (cx.tower.command()): Command
            log_record (cx.tower.command.log()): Command log record
            rendered_command_code (Text): Rendered command code.
                We are passing in case it differs from command code in the log record.
            sudo (Selection): Command sudo mode. Defaults to None.
            rendered_command_path (Char, optional): Rendered command path.
            ssh_connection (SSH client instance, optional): SSH connection to reuse.
            kwargs (dict):  extra arguments. Use to pass external values.
                Following keys are supported by default:
                    - "log": {values passed to logger}
                    - "key": {values passed to key parser}
        Returns:
            dict(): command running result if `log_record` is defined else None
        """
        response = None
        need_check_server_status = True
        if command.action == "ssh_command":
            response = self._command_runner_ssh(
                log_record=log_record,
                rendered_command_code=rendered_command_code,
                sudo=sudo,
                rendered_command_path=rendered_command_path,
                ssh_connection=ssh_connection,
                **kwargs,
            )
        elif command.action == "file_using_template":
            response = self._command_runner_file_using_template(
                log_record,
                rendered_command_path,
                **kwargs,
            )
        elif command.action == "python_code":
            response = self._command_runner_python_code(
                log_record,
                rendered_command_code,
                **kwargs,
            )
        elif command.action == "plan":
            response = self.with_context(
                prevent_plan_recursion=True
            )._command_runner_flight_plan(
                log_record,
                command.flight_plan_id,
                **kwargs,
            )
            need_check_server_status = True
        else:
            need_check_server_status = False

        if (
            need_check_server_status
            and command.server_status
            and (
                (log_record and log_record.command_status == 0)
                or (response and response["status"] == 0)
            )
        ):
            self.write({"status": command.server_status})

        if need_check_server_status:
            return response

        error_message = _(
            "No runner found for command action '%(cmd_action)s'",
            cmd_action=command.action,
        )
        if log_record:
            log_record.finish(
                finish_date=fields.Datetime.now(),
                status=NO_COMMAND_RUNNER_FOUND,
                response=None,
                error=error_message,
            )
        else:
            raise ValidationError(error_message)

    def _command_runner_file_using_template_create_file(
        self, file_template_id, server_dir, plan_line, if_file_exists, **kwargs
    ):
        """
        Creates a file on the server using the specified file template.

        This method is intended to allow overriding the file creation logic
        and provides access to the created file object.
        Args:
            file_template_id (recordset): The file template to use for creating
                the new file.
            server_dir (str): The directory on the server where the file should be
                created.
            plan_line (recordset): The plan line to use for creating
                the new file.
            if_file_exists (str): The action to take if the file already exists.
            **kwargs: Additional keyword arguments.

        Returns:
            record: The created file record.
        """
        return file_template_id.create_file(
            server=self,
            server_dir=server_dir,
            if_file_exists=if_file_exists,
        )

    def _command_runner_file_using_template(
        self,
        log_record,
        server_dir,
        **kwargs,
    ):
        """
        Run the command to create a file from a template and push to server if source
        is 'tower' and pull to tower if source is 'server'.

        This function attempts to create a new file on the server/tower using the
        specified file template. If the file creation is successful, it uploads
        the file to the server/tower. The function logs the status of the operation
        in the provided log record.

        Args:
            log_record (recordset): The log record to update with the command's
                status.
            server_dir (str): The directory on the server where the file should be
                created.
            **kwargs: Additional keyword arguments.

        Returns:
            None

        Raises:
            Exception: If any error occurs during the file creation or upload
                process, it logs the error and the exception message in the
                log record.
        """
        try:
            # Attempt to create a new file using the template for the current server
            plan_line = log_record.plan_log_id.plan_line_executed_id
            file_template_id = log_record.command_id.file_template_id
            file = self._command_runner_file_using_template_create_file(
                file_template_id=file_template_id,
                if_file_exists=log_record.command_id.if_file_exists,
                server_dir=server_dir,
                plan_line=plan_line,
            )

            # If file creation failed, log the failure and exit
            if not file:
                command_result = {
                    "status": FILE_CREATION_FAILED,
                    "response": None,
                    "error": _("File already exists"),
                }
                if log_record:
                    return log_record.finish(
                        finish_date=fields.Datetime.now(),
                        status=command_result["status"],
                        response=command_result["response"],
                        error=command_result["error"],
                    )
                else:
                    return command_result

            # Context is used to detect a retry
            # and avoid handling skip logic on first attempt
            is_creation_skipped = file._context.get("file_creation_skipped")

            if not is_creation_skipped:
                if file.source == "server":
                    file.action_pull_from_server()
                elif file.source == "tower":
                    file.action_push_to_server()
                else:
                    raise UserError(
                        _(
                            "File source cannot be determined: '%(source)s'",
                            source=file.source,
                        )
                    )

            if log_record.command_id.disconnect_file:
                file.action_unlink_from_template()

            if is_creation_skipped:
                return log_record.finish(
                    fields.Datetime.now(),
                    0,
                    _("File already exists on server. Upload skipped"),
                    None,
                )

            # Log the successful creation and upload of the file
            return log_record.finish(
                finish_date=fields.Datetime.now(),
                status=0,
                response=_("File created and uploaded successfully"),
                error=None,
            )

        except Exception as e:
            # Log any exception that occurs during the process
            log_record.finish(
                finish_date=fields.Datetime.now(),
                status=FILE_CREATION_FAILED,
                response=None,
                error=_("An error occurred: %(error)s", error=str(e)),
            )

    def _command_runner_ssh(
        self,
        log_record,
        rendered_command_code,
        sudo=None,
        rendered_command_path=None,
        ssh_connection=None,
        **kwargs,
    ):
        """Run SSH command.
        Updates the record in the Command Log (cx.tower.command.log)

        Args:
            log_record (cx.tower.command.log()): Command log record
            rendered_command_code (Text): Rendered command code.
                We are passing in case it differs from command code in the log record.
            sudo (Selection): Command sudo mode. Defaults to None.
            rendered_command_path (Char, optional): Rendered command path.
            ssh_connection (SSH client instance, optional): SSH connection to reuse.
        kwargs (dict):  extra arguments. Use to pass external values.
                Following keys are supported by default:
                    - "log": {values passed to logger}
                    - "key": {values passed to key parser}
                    - "raise_on_error": Raise exception on error.

        Returns:
            dict(): command running result if `log_record` is defined else None
        """
        raise_on_error = kwargs.pop("raise_on_error", False)
        if not ssh_connection:
            ssh_connection = self._get_ssh_client(raise_on_error=raise_on_error)

        # Run command
        command_result = self._run_command_using_ssh(
            client=ssh_connection,
            command_code=rendered_command_code,
            command_path=rendered_command_path,
            raise_on_error=raise_on_error,
            sudo=sudo,
            **kwargs,
        )

        # Log result
        if log_record:
            log_record.finish(
                finish_date=fields.Datetime.now(),
                status=command_result["status"],
                response=command_result["response"],
                error=command_result["error"],
            )
        else:
            return command_result

    def _command_runner_flight_plan(
        self, log_record, flight_plan, raise_on_error=False, **kwargs
    ):
        """
        Run Flight plan from command.
        Updates the record in the Command Log (cx.tower.command.log)
        Args:
            log_record (cx.tower.command.log()): Command log record.
            flight_plan (cx.tower.plan()): Flight Plan to be run.
            raise_on_error (bool, optional): raise error on error.
            kwargs (dict):  extra arguments. Use to pass external values.
                    Following keys are supported by default:
                        - "log": {values passed to logger}
                        - "key": {values passed to key parser}
        Returns:
            dict(): flight plan running result if `log_record` is
                    not defined else None
        """
        response = None
        error = None
        status = 0
        try:
            # Generate custom label and add values for log
            kwargs["plan_log"] = {
                "label": generate_random_id(4),
                "parent_flight_plan_log_id": log_record.plan_log_id.id,
            }
            # add executed command with action "plan" to save link to plan log
            kwargs["flight_plan_command_log"] = log_record
            plan_log_record = flight_plan.with_context(from_command=True)._run_single(
                self, **kwargs
            )
        except Exception as e:
            if raise_on_error:
                raise ValidationError(
                    _("Flight plan running error %(err)s", err=e)
                ) from e
            status = GENERAL_ERROR
            error = e
        else:
            if plan_log_record.plan_status != 0:
                status = plan_log_record.plan_status
                error = _("Flight plan running error")

        result = {"status": status, "response": response, "error": error}
        if log_record:
            log_record.finish(
                finish_date=fields.Datetime.now(),
                status=result["status"],
                response=result["response"],
                error=result["error"],
                variable_values=plan_log_record.variable_values,
            )
        else:
            return result

    def _command_runner_python_code(
        self,
        log_record,
        rendered_code,
        **kwargs,
    ):
        """
        Run Python code.
        Updates the record in the Command Log (cx.tower.command.log)

        Args:
            log_record (cx.tower.command.log()): Command log record
            rendered_code (Text): Rendered python code.
        kwargs (dict):  extra arguments. Use to pass external values.
                Following keys are supported by default:
                    - "log": {values passed to logger}
                    - "key": {values passed to key parser}

        Returns:
            dict(): python code running result if `log_record` is
                    not defined else None
        """
        # Run python code
        result = self._run_python_code(
            code=rendered_code,
            raise_on_error=False,
            **kwargs,
        )

        # Log result
        if log_record:
            log_record.finish(
                finish_date=fields.Datetime.now(),
                status=result["status"],
                response=result["response"],
                error=result["error"],
                variable_values=result["variable_values"],
            )
        else:
            return result

    @ensure_ssh_disconnect
    def _run_command_using_ssh(
        self,
        client,
        command_code,
        command_path=None,
        raise_on_error=False,
        sudo=None,
        **kwargs,
    ):
        """This is a low level method for running an SSH command.
        Use it in case you need to get direct output of an SSH command.
        Otherwise call `run_command()`

        Args:
            client (Connection): valid server ssh connection object
            command_code (Text): command text
            command_path (Char, optional): directory where command should be run
            raise_on_error (bool, optional): raise error on error
            sudo (Selection): Command sudo mode. Defaults to None. Defaults to None.
            kwargs (dict):  extra arguments. Use to pass external values.
                    Following keys are supported by default:
                        - "log": {values passed to logger}
                        - "key": {values passed to key parser}

        Raises:
            ValidationError: if client is not valid
            ValidationError: command run error

        Returns:
            dict: {
                "status": <int>,
                "response": Text,
                "error": Text
            }
        """
        if not client:
            if raise_on_error:
                raise ValidationError(_("SSH Client is not defined."))
            return {
                "status": SSH_CONNECTION_ERROR,
                "response": False,
                "error": _("SSH Client is not defined."),
            }

        # Client contains a result of _get_ssh_client()
        # If it's a tuple, it means there was an error getting the client
        if isinstance(client, tuple):
            error = client[1]
            if raise_on_error:
                raise ValidationError(error)
            return {
                "status": SSH_CONNECTION_ERROR,
                "response": False,
                "error": error,
            }

        # Parse inline secrets
        code_and_secrets = self.env["cx.tower.key"]._parse_code_and_return_key_values(
            command_code, **kwargs.get("key", {})
        )
        command_code = code_and_secrets["code"]
        secrets = code_and_secrets["key_values"]

        # Prepare ssh command
        prepared_command_code = self._prepare_ssh_command(
            command_code,
            command_path,
            sudo,
            **kwargs,
        )

        try:
            status = []
            response = []
            error = []

            # Command is a single sting. No 'sudo' or 'sudo' w/o password
            if isinstance(prepared_command_code, str):
                status, response, error = client.command_executor.exec_command(
                    prepared_command_code, sudo=sudo
                )

            # Multiple commands: sudo with password
            elif isinstance(prepared_command_code, list):
                for cmd in prepared_command_code:
                    st, resp, err = client.command_executor.exec_command(cmd, sudo=sudo)
                    status.append(st)
                    response += resp
                    error += err

            # Something weird ))
            else:
                status = [GENERAL_ERROR]

        except Exception as e:
            if raise_on_error:
                _logger.error("SSH run command error: %s", e)
                raise ValidationError(_("SSH run command error %(err)s", err=e)) from e
            status = [GENERAL_ERROR]
            response = []
            error = [e]

        result = self._parse_command_results(status, response, error, secrets, **kwargs)
        return result

    def _run_python_code(
        self,
        code,
        raise_on_error=False,
        **kwargs,
    ):
        """
        This is a low level method for Python code running.

        Args:
            code (Text): python code
            raise_on_error (bool, optional): raise error on error
            kwargs (dict):  extra arguments. Use to pass external values.
                    Following keys are supported by default:
                        - "log": {values passed to logger}
                        - "key": {values passed to key parser}

        Raises:
            ValidationError: python code running error

        Returns:
            dict: {
                "status": <int>,
                "response": Text,
                "error": Text
            }
        """
        response = None
        error = None
        status = 0
        secrets = None

        try:
            # Parse inline secrets
            code_and_secrets = self.env[
                "cx.tower.key"
            ]._parse_code_and_return_key_values(
                code, pythonic_mode=True, **kwargs.get("key", {})
            )
            secrets = code_and_secrets.get("key_values")
            command_code = code_and_secrets["code"]

            code = self.env["cx.tower.key"]._parse_code(
                command_code, pythonic_mode=True, **kwargs.get("key", {})
            )

            # Get the evaluation context for the python command
            eval_context = self.env[
                "cx.tower.command"
            ]._get_python_command_eval_context(
                server=self, variable_values=kwargs.get("variable_values", {})
            )

            safe_eval(
                code,
                eval_context,
                mode="exec",
                nocopy=True,
            )
            kwargs["variable_values"] = eval_context.get("custom_values", {})
            result = eval_context.get("result")
            if result:
                status = result.get("exit_code", 0)
                if status == 0:
                    response = [result.get("message")]
                else:
                    error = [result.get("message")]

        except Exception as e:
            if raise_on_error:
                raise ValidationError(
                    _("Python code running error: %(err)s", err=e)
                ) from e
            else:
                status = PYTHON_COMMAND_ERROR
                error = [e]

        result = self._parse_command_results(status, response, error, secrets, **kwargs)
        result["variable_values"] = kwargs.get("variable_values", {})
        return result

    def _prepare_ssh_command(self, command_code, path=None, sudo=None, **kwargs):
        """Prepare ssh command
        IMPORTANT:
        Commands run with sudo will be run separately one after another
        even if there is a single command separated with '&&'
        Examples:
            # Default (sudo with splitting):
            "pwd && ls -l" becomes:
                sudo pwd
                sudo ls -l

            # With no_split_for_sudo=True:
                sudo pwd && ls -l

        Args:
            command_code (str): initial command
            path (str, optional): directory where command should be run
            sudo (str, optional): sudo mode ('n' or 'p')
                'n' — sudo without password
                'p' — sudo with password
            kwargs (dict): extra arguments. Supported keys:
                - "log": values passed to logger
                - "key": values passed to key parser
                - "no_split_for_sudo" (bool): if True, do not split on '&&'

        Returns:
            list or str: if sudo='p' (with password), returns a list of commands;
                if sudo='n', returns a single string (possibly joined by '&&');
                without sudo, returns the raw command_code.
        """
        # Prepare command for sudo if needed
        if sudo:
            # Add location
            sudo_prefix = "sudo -S -p ''"

            no_split = kwargs.get("no_split_for_sudo", False)

            separator = "&&"
            # split only when '&&' is present AND splitting is not disabled
            if separator in command_code and not no_split:
                result = (
                    command_code.replace("\\", "").replace("\n", "").split(separator)
                )

                # Sudo with password expects a list of commands
                result = [f"{sudo_prefix} {cmd.strip()}" for cmd in result]

                # Merge back into a single command is sudo is without password
                if sudo == "n":
                    result = f" {separator} ".join(result)
            else:
                # single command or no_split requested
                result = f"{sudo_prefix} {command_code}"
                # Sudo with password expects a list of commands
                if sudo == "p":
                    result = [result]
        else:
            # Command without sudo is always run as is
            result = command_code
        # Add path change command
        if path:
            # Add sudo prefix if needed
            cd_command = f"cd {path}"

            if isinstance(result, list):
                result = [cd_command] + result
            else:
                result = f"{cd_command} && {result}"

        return result

    def _parse_command_results(
        self, status, response, error, key_values=None, **kwargs
    ):
        """
        Parse results of a command run with sudo (either SSH or Python).
        Removes secrets and formats the response and error messages.

        Paramiko returns SSH response and error as list.
        When running a command with sudo with password we return status as a list too.
        _

        Args:
            status (Int or list of int): Status or statuses
            response (list): Response
            error (list): Error
            key_values (list): Secrets that were discovered in code.
                Used to clean up command result.
            kwargs (dict):  extra arguments. Use to pass external values.
                Following keys are supported by default:
                    - "log": {values passed to logger}
                    - "key": {values passed to key parser}

        Returns:
            dict: {
                "status": <int>,
                "response": <text>,
                "error": <text>
            }
        """

        # In case of several statuses we return the last one that is not 0 ("ok")
        # Eg for [0,1,0,4,0] result will be 4
        if isinstance(status, list):
            final_status = 0
            for st in status:
                if st != 0:
                    final_status = st

            status = final_status

        # This is needed to remove keys
        if key_values:
            key_model = self.env["cx.tower.key"]

        # Compose response message
        if response and isinstance(response, list):
            # Replace secrets with spoiler
            response_vals = [
                key_model._replace_with_spoiler(str(r), key_values)
                if key_values
                else str(r)
                for r in response
            ]
            response = "".join(response_vals)

        elif not response:
            # For not to save an empty list `[]` in log
            response = None

        # Compose error message
        if error and isinstance(error, list):
            # Replace secrets with spoiler
            error_vals = [
                key_model._replace_with_spoiler(str(e), key_values)
                if key_values
                else str(e)
                for e in error
            ]
            error = "".join(error_vals)
        elif not error:
            # For not to save an empty list `[]` in log
            error = None

        return {
            "status": status,
            "response": response,
            "error": error,
        }

    def _check_zombie_commands(self):
        """
        Check commands that are running longer than the timeout
        and mark them as finished
        """
        timeout = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("cetmix_tower_server.command_timeout", 0)
        )
        if not timeout:
            return

        # SSH or Python command is running longer than the timeout
        # We are not terminating Flight Plans and File Upload commands
        domain = [
            ("is_running", "=", True),
            ("start_date", "<", fields.Datetime.now() - timedelta(seconds=timeout)),
            ("command_action", "in", ["ssh_command", "python_code"]),
        ]
        zombie_command_logs = self.env["cx.tower.command.log"].search(domain)
        if zombie_command_logs:
            zombie_command_logs.finish(
                status=COMMAND_TIMED_OUT,
                response=None,
                error=COMMAND_TIMED_OUT_MESSAGE,
            )

    # ------------------------------
    # ---- File management
    # ------------------------------

    @ensure_ssh_disconnect
    def delete_file(self, remote_path):
        """
        Delete file from remote server

        Args:
            remote_path (Text): full path file location with file type
             (e.g. /test/my_file.txt).
        """
        self.ensure_one()
        client = self._get_ssh_client(raise_on_error=True)
        client.sftp_service.delete_file(remote_path)

    @ensure_ssh_disconnect
    def upload_file(self, data, remote_path, from_path=False):
        """
        Upload file to remote server.

        Args:
            data (Text, Bytes): If the data are text, they are converted to bytes,
                                contains a local file path if from_path=True.
            remote_path (Text): full path file location with file type
             (e.g. /test/my_file.txt).
            from_path (Boolean): set True if `data` is file path.

        Raise:
            TypeError: incorrect type of file.

        Returns:
            Result (class paramiko.sftp_attr.SFTPAttributes): metadata of the
             uploaded file.
        """
        self.ensure_one()
        client = self._get_ssh_client(raise_on_error=True)
        if from_path:
            result = client.sftp_service.upload_file(data, remote_path)
        else:
            # Convert string to bytes
            if isinstance(data, str):
                data = data.encode()
            file = io.BytesIO(data)
            result = client.sftp_service.upload_file(file, remote_path)

        return result

    @ensure_ssh_disconnect
    def download_file(self, remote_path):
        """
        Download file from remote server

        Args:
            remote_path (Text): full path file location with file type
             (e.g. /test/my_file.txt).

        Raise:
            ValidationError: raise if file not found.

        Returns:
            Result (Bytes): file content.
        """
        self.ensure_one()
        client = self._get_ssh_client(raise_on_error=True)
        try:
            result = client.sftp_service.download_file(remote_path)

        except FileNotFoundError as fe:
            raise ValidationError(
                _("The file %(f_path)s not found.", f_path=remote_path)
            ) from fe
        return result

    # ------------------------------
    # ---- Auxiliary functions
    # ------------------------------

    def server_toggle_active(self, self_active):
        """
        Change active status of related records

        Args:
            self_active (bool): active status of the record
        """
        self.file_ids.filtered(lambda f: f.active == self_active).toggle_active()
        self.command_log_ids.filtered(lambda c: c.active == self_active).toggle_active()
        self.plan_log_ids.filtered(lambda p: p.active == self_active).toggle_active()
        self.variable_value_ids.filtered(
            lambda vv: vv.active == self_active
        ).toggle_active()

    def toggle_active(self):
        """Archiving related server"""
        res = super().toggle_active()
        server_active = self.with_context(active_test=False).filtered(
            lambda x: x.active
        )
        server_not_active = self - server_active
        if server_active:
            server_active.server_toggle_active(False)
        if server_not_active:
            server_not_active.server_toggle_active(True)
        return res

    def _is_being_deleted(self):
        """Check if the server is being deleted.

        Returns:
            bool: True if the server is being deleted, False otherwise
        """
        self.ensure_one()
        return self.status and self.status == "deleting"

    def _get_post_create_fields(self):
        """
        Add fields that should be populated after server creation
        """
        res = super()._get_post_create_fields()
        return res + ["variable_value_ids", "server_log_ids", "secret_ids"]

    def _get_notification_action(
        self, message, notification_type="info", title=None, sticky=True
    ):
        """Get notification action

        Args:
            message (str): Message
            notification_type (str, optional): Notification type. Defaults to "info".
            title (str, optional): Title. Defaults to None.
            sticky (bool, optional): Sticky notification. Defaults to True.

        Returns:
            dict: Notification action
        """
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": notification_type,
                "title": title,
                "message": message,
                "sticky": sticky,
            },
        }

    def _get_dependent_model_relation_fields(self):
        """Check cx.tower.reference.mixin for the function documentation"""
        res = super()._get_dependent_model_relation_fields()
        return res + ["variable_value_ids", "file_ids"]
