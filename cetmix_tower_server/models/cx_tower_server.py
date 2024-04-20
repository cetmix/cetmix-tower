# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import ast
import io
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .constants import ANOTHER_COMMAND_RUNNING

_logger = logging.getLogger(__name__)


try:
    from paramiko import AutoAddPolicy, RSAKey, SFTPClient, SSHClient
except ImportError:
    _logger.error(
        "import 'paramiko' error, please try to install: pip install paramiko"
    )
    AutoAddPolicy = RSAKey = SSHClient = None


class SSH(object):
    """
    This is a class for communicating with remote servers via SSH.
    """

    def __init__(
        self,
        host,
        port,
        username,
        password=None,
        ssh_key=None,
        mode="p",
        allow_agent=False,
        timeout=5000,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.mode = mode
        self.password = password
        self.ssh_key = ssh_key
        self.timeout = timeout
        # NB: allow_agent=False is for avoiding
        # ssh-agent related connection issues~
        self.allow_agent = allow_agent

        self._ssh = None
        self._sftp = None

    def __del__(self):
        """
        Close connection after executing methods
        """
        self.disconnect()

    def _get_ssh_key(self):
        """
        Get ssh key

        This function prepares and returns ssh key for the ssh connection

        Returns:
            Char: password ready to be used for connection parameters
        """
        ssh_key = RSAKey.from_private_key(io.StringIO(self.ssh_key))
        return ssh_key

    def _connect(self):
        """
        Connect to remote host
        """
        self._ssh = SSHClient()
        self._ssh.load_system_host_keys()
        self._ssh.set_missing_host_key_policy(AutoAddPolicy())
        kwargs = {
            "hostname": self.host,
            "port": self.port,
            "username": self.username,
            "allow_agent": self.allow_agent,
            "timeout": self.timeout,
        }
        if self.mode == "p":
            kwargs.update(
                {
                    "password": self.password,
                }
            )
        elif self.mode == "k":
            kwargs.update(
                {
                    "pkey": self._get_ssh_key(),
                }
            )
        self._ssh.connect(**kwargs)
        return self._ssh

    @property
    def connection(self):
        """
        Open SSH connection to remote host.
        """
        return self._connect()

    @property
    def sftp(self):
        """
        Open SFTP connection to remote host.
        """
        self._sftp = SFTPClient.from_transport(self.connection.get_transport())
        return self._sftp

    def disconnect(self):
        """
        Close SSH & SFTP connection.
        """
        logger = logging.getLogger("paramiko")
        if self._ssh:
            logger.info("Disconnect SSH connection")
            self._ssh.close()
        if self._sftp:
            logger.info("Disconnect SFTP connection")
            self._sftp.close()

    def exec_command(self, command, sudo=None):
        """_summary_

        Args:
            command (text): Command text
            sudo (selection): Use sudo
                - 'n': no password
                - 'p': with password
                - Defaults to None.

        Returns:
            status, response, error
        """
        # TODO: check this
        # https://stackoverflow.com/questions/22587855/running-sudo-command-with-paramiko
        if sudo and self.username != "root":
            command = "sudo -S -p '' %s" % command

        stdin, stdout, stderr = self.connection.exec_command(command)
        if sudo == "p":
            if not self.password:
                error_message = [_("sudo password was not provided!")]
                return 255, [], error_message
            stdin.write(self.password + "\n")
            stdin.flush()
        status = stdout.channel.recv_exit_status()
        response = stdout.readlines()
        error = stderr.readlines()
        return status, response, error

    def upload_file(self, file, remote_path):
        """
        Upload file to remote server.

        Args:
            file (Text, Bytes): If bytes - file presented as contents of an
                                open file object (fl).
                                if text - file presented as local path to file
            remote_path (Text): full path file location with file type
            (e.g. /test/my_file.txt).

        Raise:
            TypeError: incorrect type of file.

        Returns:
            Result (class paramiko.sftp_attr.SFTPAttributes): metadata
             of the uploaded file.
        """
        if isinstance(file, io.BytesIO):
            result = self.sftp.putfo(file, remote_path)
        elif isinstance(file, str):
            result = self.sftp.put(file, remote_path=remote_path, recursive=True)
        else:
            raise TypeError(
                "Incorrect type of file ({}) allowed: string, BytesIO.".format(
                    type(file).__name__
                )
            )
        return result

    def download_file(self, remote_path):
        """
        Download file from remote server

        Args:
            remote_path (Text): full path file location with file type
             (e.g. /test/my_file.txt).

        Returns:
            Result (Bytes): file content.
        """
        file = self.sftp.open(remote_path)
        return file.read()

    def move_file(self, old_path, new_path):
        """
        Rename/Move file from old path to new path on remote server

        Args:
            old_path (Text): full path file location with file type
             (e.g. /test/my_file.txt).
            new_path (Text): full path file location with file type
             (e.g. /test/my_new_file.txt).
        """
        self.sftp.rename(old_path, new_path)


class CxTowerServer(models.Model):
    """Represents a server entity

    Keeps information required to connect and perform routine operations
    such as configuration, file management etc"

    """

    _name = "cx.tower.server"
    _inherit = ["cx.tower.variable.mixin", "mail.thread", "mail.activity.mixin"]
    _description = "Cetmix Tower Server"
    _order = "name asc"

    # ---- Main
    active = fields.Boolean(default=True)
    name = fields.Char(string="Name", required=True)
    color = fields.Integer(string="Color", help="For better visualization in views")
    partner_id = fields.Many2one(string="Partner", comodel_name="res.partner")

    # ---- Connection
    ip_v4_address = fields.Char(string="IPv4 Address")
    ip_v6_address = fields.Char(string="IPv6 Address")
    ssh_port = fields.Char(string="SSH port", required=True, default="22")
    ssh_username = fields.Char(string="SSH Username", required=True)
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
        default="p",
        required=True,
    )
    use_sudo = fields.Selection(
        string="Use sudo",
        selection=[("n", "Without password"), ("p", "With password")],
        help="Run commands using 'sudo'",
    )
    # ---- Variables
    variable_value_ids = fields.One2many(
        inverse_name="server_id"  # Other field properties are defined in mixin
    )

    # ---- Keys
    secret_ids = fields.One2many(
        string="Secrets",
        comodel_name="cx.tower.key",
        inverse_name="server_id",
        domain=[("key_type", "!=", "k")],
    )

    # ---- Attributes
    os_id = fields.Many2one(string="Operating System", comodel_name="cx.tower.os")
    tag_ids = fields.Many2many(
        comodel_name="cx.tower.tag",
        relation="cx_tower_server_tag_rel",
        column1="server_id",
        column2="tag_id",
        string="Tags",
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
        super().toggle_active()
        server_active = self.with_context(active_test=False).filtered(
            lambda x: x.active
        )
        server_not_active = self - server_active
        if server_active:
            server_active.server_toggle_active(False)
        if server_not_active:
            server_not_active.server_toggle_active(True)

    def _compute_file_count(self):
        """Compute total server files"""
        for server in self:
            server.file_count = len(server.file_ids)

    @api.constrains("ip_v4_address", "ip_v6_address", "ssh_auth_mode")
    def _constraint_ssh_settings(self):
        """Ensure SSH settings are valid"""
        for rec in self:
            if not rec.ip_v4_address and not rec.ip_v6_address:
                raise ValidationError(
                    _("Please provide IPv4 or IPv6 address for %s" % rec.name)
                )
            if rec.ssh_auth_mode == "p" and not rec.ssh_password:
                raise ValidationError(
                    _("Please provide SSH password for %s" % rec.name)
                )
            if rec.ssh_auth_mode == "k" and not rec.ssh_key_id:
                raise ValidationError(_("Please provide SSH Key for %s" % rec.name))

    @api.returns("self", lambda value: value.id)
    def copy(self, default=None):
        default = default or {}
        default["name"] = _("%s (copy)", self.name)

        file_ids = self.env["cx.tower.file"]
        for file in self.file_ids:
            file_ids |= file.copy({"auto_sync": False})
        default["file_ids"] = file_ids.ids

        result = super(CxTowerServer, self).copy(default=default)

        for secret in self.secret_ids:
            secret.sudo().copy({"server_id": result.id})

        for var_value in self.variable_value_ids:
            var_value.copy({"server_id": result.id})

        return result

    def action_open_command_logs(self):
        """
        Open current server command log records
        """
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_command_log"
        )
        action["domain"] = [("server_id", "=", self.id)]
        return action

    def action_open_plan_logs(self):
        """
        Open current server flightplan log records
        """
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.action_cx_tower_plan_log"
        )
        action["domain"] = [("server_id", "=", self.id)]
        return action

    def _get_password(self):
        """Get ssh password
        This function prepares and returns ssh password for the ssh connection
        Override this function to implement own password algorithms

        Returns:
            Char: password ready to be used for connection parameters
        """
        self.ensure_one()
        password = self.ssh_password
        return password

    def _get_ssh_key(self):
        """Get SSH key
        Get private key for an SSH connection

        Returns:
            Char: SSH private key
        """
        self.ensure_one()
        if self.ssh_key_id:
            ssh_key = self.ssh_key_id.sudo().secret_value
        else:
            ssh_key = None
        return ssh_key

    def _get_connection_test_command(self):
        """Get command used to test SSH connection

        Returns:
            Char: SSH command
        """
        command = "whoami"
        return command

    def _connect(self, raise_on_error=True):
        """_summary_

        Args:
            raise_on_error (bool, optional): If true will raise exception
             in case or error, otherwise False will be returned
            Defaults to True.
        """
        self.ensure_one()
        try:
            client = SSH(
                host=self.ip_v4_address or self.ip_v6_address,
                port=self.ssh_port,
                username=self.ssh_username,
                mode=self.ssh_auth_mode,
                password=self._get_password(),
                ssh_key=self._get_ssh_key(),
            )
        except Exception as e:
            if raise_on_error:
                raise ValidationError(_("SSH connection error %s" % e)) from e
            else:
                return False, e
        return client

    def test_ssh_connection(self):
        """Test SSH connection"""
        self.ensure_one()
        client = self._connect()
        command = self._get_connection_test_command()
        status, response, error = self._execute_command(client, command=command)

        if status != 0 or error:
            raise ValidationError(
                _(
                    "Cannot execute command\n. CODE: {}. RESULT: {}. ERROR: {}".format(
                        status, response, ", ".join(error)
                    )
                )
            )

        if not response:
            raise ValidationError(
                _(
                    "No output received."
                    " Please log in manually and check for any issues.\n"
                    "===\nCODE: {}".format(status)
                )
            )

        # test upload file
        self.upload_file("test", "/var/tmp/test.txt")

        # test download loaded file
        self.download_file("/var/tmp/test.txt")

        # remove file from server
        st, resp, err = self._execute_command(
            client, command="rm -rf /var/tmp/test.txt"
        )
        if status != 0 or error:
            raise ValidationError(
                _(
                    "Cannot execute command\n. CODE: {}. ERROR: {}".format(
                        st, ", ".joint(err)
                    )
                )
            )

        notification = {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": _("Connection test passed! \n{}".format(response)),
                "sticky": False,
            },
        }
        return notification

    def _pre_execute_commands(self, commands, variables=None, sudo=None, **kwargs):
        """Will be triggered before command execution.
        Inherit to tweak command values

        Args:
            commands (cx.tower.command): Command recordset
            variables (dict): {command.id: [variables]}
            sudo (section): use sudo (refer to field). Defaults to None
            kwargs (dict):  extra arguments. Use to pass external values.
                Following keys are supported by default:
                    - "log": {values passed to logger}
                    - "key": {values passed to key parser}

        Returns:
            commands, variables, sudo
        """
        return commands, variables, sudo, kwargs

    def execute_commands(self, commands, sudo=None, **kwargs):
        """This is a main function to use for commands
            and the wrapper function for _execute commands()
        Used to execute multiple commands on multiple servers.
        This is a primary function to be used for executing commands.

        Args:
            commands (cx.tower.command()): Command recordset
            sudo (selection): use sudo
                None - do not use sudo
                'n' - no password
                'p' - with password
                Defaults to None
            kwargs (dict):  extra arguments. Use to pass external values.
                Following keys are supported by default:
                    - "log": {values passed to logger}
                    - "key": {values passed to key parser}
        """

        # Get variables from commands {command.id: [variables]}
        variables = commands.get_variables()

        # Run pre-command hook
        commands, variables, sudo, kwargs = self._pre_execute_commands(
            commands, variables, sudo, **kwargs
        )

        # Execute commands
        for server in self:
            server._execute_commands_on_server(commands, variables, sudo, **kwargs)

    def _execute_commands_on_server(
        self, commands, variables=None, sudo=None, **kwargs
    ):
        """Execute multiple commands on selected server.

        Args:
            commands (cx.tower.command()): Command recordset
            variable (List): Variables to render the commands with
            sudo (section): use sudo (refer to field). Defaults to None.
            kwargs (dict):  extra arguments. Use for extending
        """
        self.ensure_one()
        client = self._connect(raise_on_error=False)
        log_obj = self.env["cx.tower.command.log"]
        # Prepare log vals
        log_vals_common = kwargs.get("log", {})  # Get vals from kwargs
        log_vals_common.update({"use_sudo": sudo})
        for command in commands:
            # Init log vals
            log_vals = log_vals_common.copy()

            # Check if command is already running and parallel run is not allowed
            if not command.allow_parallel_run:
                running_count = log_obj.sudo().search_count(
                    [
                        ("server_id", "=", self.id),
                        ("command_id", "=", command.id),
                        ("is_running", "=", True),
                    ]
                )
                # Create log record and continue to the next one
                # if the same command is currently running on the same server
                # Log result
                if running_count > 0:
                    now = fields.Datetime.now()
                    log_obj.record(
                        self.id,
                        command.id,
                        now,
                        now,
                        ANOTHER_COMMAND_RUNNING,
                        None,
                        [_("Another instance of the command is running already")],
                        **log_vals,
                    )
                    continue

            # Get variable values for server
            variable_values = (
                self.get_variable_values(variables.get(str(command.id)))
                if variables
                else False
            )

            # Render command code using variables
            if variable_values:
                rendered_code = command.render_code(**variable_values.get(self.id)).get(
                    command.id
                )
            else:
                rendered_code = command.code

            # Save rendered code to log
            log_vals.update({"code": rendered_code})

            # Prepare key renderer values
            key_vals = kwargs.get("key", {})  # Get vals from kwargs
            key_vals.update({"server_id": self.id})
            if self.partner_id:
                key_vals.update({"partner_id": self.partner_id.id})

            # Create log record
            log_record = log_obj.start(self.id, command.id, **log_vals)

            # Execute command
            status, response, error = self._execute_command(
                client, rendered_code, False, sudo
            )

            # Log result
            log_record.finish(fields.Datetime.now(), status, response, error)

    def _execute_command(
        self, client, command, raise_on_error=True, sudo=None, **kwargs
    ):
        """Execute a single command using existing connection

        Args:
            client (Connection): valid server connection obj
            command (Text): command text
            raise_on_error (bool, optional): raise error on error
            sudo (selection): use sudo Defaults to None.

        Raises:
            ValidationError: if client is not valid
            ValidationError: command execution error

        Returns:
            status, [response], [error]
        """
        if not client:
            raise ValidationError(_("SSH Client is not defined."))

        # Parse inline variables
        command = self.env["cx.tower.key"].parse_code(command, **kwargs.get("key", {}))

        try:
            if sudo:  # Execute each command separately to avoid extra shell
                status = []
                response = []
                error = []
                for cmd in self._prepare_command_for_sudo(command):
                    st, resp, err = client.exec_command(cmd, sudo=sudo)
                    status.append(st)
                    response += resp
                    error += err
                return self._parse_sudo_command_results(status, response, error)
            else:
                result = client.exec_command(command, sudo=sudo)
        except Exception as e:
            if raise_on_error:
                raise ValidationError(_("SSH execute command error %s" % e)) from e
            else:
                return -1, [], [e]
        return result

    def _prepare_command_for_sudo(self, command):
        """Prepare command to be executed with sudo
        IMPORTANT:
        Commands executed with sudo will be run separately one after another
        even if there is a single command separated with '&&' or ';'
        Example:
        "pwd && ls -l" will be executed as:
            sudo pwd
            sudo ls -l

        Args:
            command (text): initial command

        Returns:
            command (list): command splitted into separate commands

        """
        # Detect command separator
        if "&&" in command:
            separator = "&&"
        elif ";" in command:
            separator = ";"
        else:
            return [command]

        return command.replace("\\", "").replace("\n", "").split(separator)

    def _parse_sudo_command_results(self, status_list, response_list, error_list):
        """Parse results of the command executed with sudo

        Args:
            status_list (list): List of statuses
            response_list (list): List of responses
            error_list (_type_): list of errors

        Returns:
            int, list, list: status, response, error
        """
        status = 0
        for st in status_list:
            if st != 0 and st != status:
                status = st

        return status, response_list, error_list

    def action_execute_command(self):
        """
        Returns wizard action to select command and execute it
        """
        context = self.env.context.copy()
        context.update(
            {
                "default_server_ids": self.ids,
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

    def action_execute_plan(self):
        """
        Returns wizard action to select flightplan and execute it
        """
        context = self.env.context.copy()
        context.update(
            {
                "default_server_ids": self.ids,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Execute Flight Plan"),
            "res_model": "cx.tower.plan.execute.wizard",
            "view_mode": "form",
            "view_type": "form",
            "target": "new",
            "context": context,
        }

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
        client = self._connect(raise_on_error=False)
        if from_path:
            result = client.upload_file(data, remote_path)
        else:
            if isinstance(data, str):
                data = str.encode(data)
            if not isinstance(data, bytes):
                raise TypeError(
                    "Incorrect type of file ({}) allowed: string, bytes.".format(
                        type(data).__name__
                    )
                )
            file = io.BytesIO(data)
            file.seek(0)
            result = client.upload_file(file, remote_path)
        return result

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
        client = self._connect(raise_on_error=False)
        try:
            result = client.download_file(remote_path)
        except FileNotFoundError as fe:
            raise ValidationError(
                _('The file "{}" not found.'.format(remote_path))
            ) from fe
        return result

    def rename_file(self, old_path, new_path):
        """
        Rename/Move file from old path to new path on remote server

        Args:
            old_path (Text): full path file location with file type
             (e.g. /test/my_file.txt).
            new_path (Text): full path file location with file type
             (e.g. /test/my_new_file.txt).
        """
        self.ensure_one()
        client = self._connect(raise_on_error=False)
        client.move_file(old_path, new_path)

    def action_open_files(self):
        """
        Open current server files
        """
        action = self.env["ir.actions.actions"]._for_xml_id(
            "cetmix_tower_server.cx_tower_file_action"
        )
        action["domain"] = [("server_id", "=", self.id)]

        context = self._context.copy()
        if "context" in action and isinstance((action["context"]), str):
            context.update(ast.literal_eval(action["context"]))
        else:
            context.update(action.get("context", {}))

        context.update(
            {
                "default_server_id": self.id,
            }
        )
        action["context"] = context
        return action
