# Copyright (C) 2022 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import ast
import io
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval

from .constants import (
    ANOTHER_COMMAND_RUNNING,
    FILE_CREATION_FAILED,
    NO_COMMAND_RUNNER_FOUND,
    PYTHON_COMMAND_ERROR,
)

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
        ssh_key = RSAKey.from_private_key(io.StringIO(self.ssh_key))  # type: ignore
        return ssh_key

    def _connect(self):
        """
        Connect to remote host
        """
        self._ssh = SSHClient()  # type: ignore
        self._ssh.load_system_host_keys()
        self._ssh.set_missing_host_key_policy(AutoAddPolicy())  # type: ignore
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
        self._sftp = SFTPClient.from_transport(self.connection.get_transport())  # type: ignore
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
        # Check this
        # https://stackoverflow.com/questions/22587855/running-sudo-command-with-paramiko

        sudo_with_password = sudo == "p" and self.username != "root"
        if sudo_with_password:
            # Return error if password is not set
            if not self.password:
                error_message = [_("sudo password was not provided!")]
                return 255, [], error_message

        stdin, stdout, stderr = self.connection.exec_command(command)

        # Send password to stdin
        if sudo_with_password:
            stdin.write(self.password + "\n")  # type: ignore
            stdin.flush()
            # TODO: add password error check

        status = stdout.channel.recv_exit_status()
        response = stdout.readlines()
        error = stderr.readlines()
        return status, response, error

    def delete_file(self, remote_path):
        """
        Delete file from remote server

        Args:
            remote_path (Text): full path file location with file type
             (e.g. /test/my_file.txt).
        """
        self.sftp.remove(remote_path)

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
    partner_id = fields.Many2one(
        string="Partner",
        comodel_name="res.partner",
        ondelete="restrict",
    )
    status = fields.Selection(
        selection=lambda self: self._selection_status(),
        default=lambda self: self._default_status(),
        required=True,
    )

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
        ondelete="restrict",
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
    os_id = fields.Many2one(
        string="Operating System",
        comodel_name="cx.tower.os",
        ondelete="restrict",
    )
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

    # ---- Server logs
    server_log_ids = fields.One2many(
        string="Server Logs",
        comodel_name="cx.tower.server.log",
        inverse_name="server_id",
    )

    def _selection_status(self):
        """
        Status selection options

        Returns:
            list: status selection options
        """
        return [
            ("1", "Undefined"),
            ("2", "Stopped"),
            ("3", "Starting"),
            ("4", "Running"),
            ("5", "Stopping"),
            ("6", "Restarting"),
        ]

    def _default_status(self):
        """
        Default status

        Returns:
            str: default status
        """
        return "1"

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
                    _("Please provide IPv4 or IPv6 address for %(srv)s", srv=rec.name)
                )
            if rec.ssh_auth_mode == "p" and not rec.ssh_password:
                raise ValidationError(
                    _("Please provide SSH password for %(srv)s", srv=rec.name)
                )
            if rec.ssh_auth_mode == "k" and not rec.ssh_key_id:
                raise ValidationError(
                    _("Please provide SSH Key for %(srv)s", srv=rec.name)
                )

    @api.returns("self", lambda value: value.id)
    def copy(self, default=None):
        default = default or {}
        default["name"] = _("%(name)s (copy)", name=self.name)

        file_ids = self.env["cx.tower.file"]
        for file in self.file_ids:
            file_ids |= file.copy(
                {
                    "auto_sync": False,
                    "keep_when_deleted": True,
                }
            )
        default["file_ids"] = file_ids.ids

        result = super(CxTowerServer, self).copy(default=default)

        for secret in self.secret_ids:
            secret.sudo().copy({"server_id": result.id})

        for var_value in self.variable_value_ids:
            var_value.copy({"server_id": result.id})

        return result

    def action_update_server_logs(self):
        """Update selected log from its source."""
        for server in self:
            if server.server_log_ids:
                server.server_log_ids.action_get_log_text()

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
        command = "uname -a"
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
                raise ValidationError(_("SSH connection error %(err)s", err=e)) from e
            else:
                return False, e
        return client

    def test_ssh_connection(self):
        """Test SSH connection"""
        self.ensure_one()
        client = self._connect()
        command = self._get_connection_test_command()
        command_result = self._execute_command_using_ssh(client, command_code=command)

        if command_result["status"] != 0 or command_result["error"]:
            raise ValidationError(
                _(
                    "Cannot execute command\n. CODE: %(status)s. "
                    "RESULT: %(res)s. ERROR: %(err)s",
                    status=command_result["status"],
                    res=command_result["response"],
                    err=command_result["error"],  # type: ignore
                )
            )

        if not command_result["response"]:
            raise ValidationError(
                _(
                    "No output received."
                    " Please log in manually and check for any issues.\n"
                    "===\nCODE: %(status)s",
                    status=command_result["status"],
                )
            )

        # test upload file
        self.upload_file("test", "/var/tmp/test.txt")

        # test download loaded file
        self.download_file("/var/tmp/test.txt")

        # remove file from server
        file_remove_result = self._execute_command_using_ssh(
            client, command_code="rm -rf /var/tmp/test.txt"
        )
        if file_remove_result["status"] != 0 or command_result["error"]:
            raise ValidationError(
                _(
                    "Cannot execute command\n. CODE: %(status)s. ERROR: %(err)s",
                    err=file_remove_result["error"],  # type: ignore
                    status=file_remove_result["status"],
                )
            )

        notification = {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": _(
                    "Connection test passed! \n%(res)s",
                    res=command_result["response"].rstrip(),
                ),
                "sticky": False,
            },
        }
        return notification

    def _render_command(self, command, path=None):
        """Renders command code for selected command for current server

        Args:
            command (cx.tower.command): Command to render
            path (Char): Path where to execute the command.
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
            self.get_variable_values(variables)  # pylint: disable=no-member
            if variables
            else False
        )

        # Extract variable values for current server
        variable_values = (
            variable_values_dict.get(self.id) if variable_values_dict else False
        )  # pylint: disable=no-member

        # Render command code using variables
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

    def execute_command(
        self, command, path=None, sudo=None, ssh_connection=None, **kwargs
    ):
        """This is the main function to use for running commands.
        It renders command code, creates log record and calls command runner.

        Args:
            command (cx.tower.command()): Command record
            path (Char): directory where command is run.
                Provide in case you need to override default command value
            sudo (selection): use sudo
                None - do not use sudo
                'n' - no password
                'p' - with password
                Defaults to None
            ssh_connection (SSH client instance, optional): SSH connection.
                Pass to reuse existing connection.
                This is useful in case you would like to speed up
                the ssh command execution.
            kwargs (dict):  extra arguments. Use to pass external values.
                Following keys are supported by default:
                    - "log": {values passed to logger}
                    - "key": {values passed to key parser}
        Context:
            no_log (Bool): set this context key to `True` to disable log creation.
            Command execution results will be returned instead.
            If any non command related error occurs in the command execution flow
            an exception will be raised.
            IMPORTANT: be aware when running commands with `no_log=True`
            because no `Allow Parallel Run` check will be done!
        Returns:
            dict(): command execution result if `no_log` context value == True else None
        """
        self.ensure_one()

        # Populate `sudo` value from the server settings if not provided explicitly
        if sudo is None:
            if self.ssh_username != "root" and self.use_sudo:
                sudo = self.use_sudo

        # Disable `sudo` if user is root
        elif sudo and self.ssh_username == "root":
            sudo = None

        # Check if no log record should be created

        no_log = self._context.get("no_log")

        # Get log vals from kwargs and update them
        if not no_log:
            log_obj = self.env["cx.tower.command.log"]
            log_vals = kwargs.get("log", {})
            log_vals.update({"use_sudo": sudo})

            # Check if command is already running and parallel run is not allowed
            if not command.allow_parallel_run:
                running_count = log_obj.sudo().search_count(
                    [
                        ("server_id", "=", self.id),  # pylint: disable=no-member
                        ("command_id", "=", command.id),
                        ("is_running", "=", True),
                    ]
                )
                # Create log record and exit
                # if the same command is currently running on the same server
                if running_count > 0:
                    now = fields.Datetime.now()
                    log_obj.record(
                        self.id,  # pylint: disable=no-member
                        command.id,
                        now,
                        now,
                        ANOTHER_COMMAND_RUNNING,
                        None,
                        [_("Another instance of the command is already running")],
                        **log_vals,
                    )
                    return

        # Render command
        rendered_command = self._render_command(command, path)
        rendered_command_code = rendered_command["rendered_code"]
        rendered_command_path = rendered_command["rendered_path"]

        # Prepare key renderer values
        key_vals = kwargs.get("key", {})  # Get vals from kwargs
        key_vals.update({"server_id": self.id})  # pylint: disable=no-member
        if self.partner_id:
            key_vals.update({"partner_id": self.partner_id.id})

        # Save rendered code to log
        if no_log:
            log_record = None
        else:
            log_vals.update(
                {"code": rendered_command_code, "path": rendered_command_path}
            )
            # Create log record
            log_record = log_obj.start(self.id, command.id, **log_vals)  # pylint: disable=no-member

        return self.with_context(use_sudo=sudo)._command_runner_wrapper(
            command,
            log_record,
            rendered_command_code,
            rendered_command_path,
            ssh_connection,
            **kwargs,
        )

    def _command_runner_wrapper(
        self,
        command,
        log_record,
        rendered_command_code,
        rendered_command_path=None,
        ssh_connection=None,
        **kwargs,
    ):
        """Used to implement custom runner mechanisms.\
        Use it in case you need to redefine the entire command execution engine.
        Eg it's used in `cetmix_tower_server_queue` OCA `queue_job` implementation.

        Args:
            command (cx.tower.command()): Command
            log_record (cx.tower.command.log()): Command log record
            rendered_command_code (Text): Rendered command code.
                We are passing in case it differs from command code in the log record.
            rendered_command_path (Char, optional): Rendered command path.
            ssh_connection (SSH client instance, optional): SSH connection to reuse.
        kwargs (dict):  extra arguments. Use to pass external values.
                Following keys are supported by default:
                    - "log": {values passed to logger}
                    - "key": {values passed to key parser}

        Context:
            use_sudo (Bool): use sudo for command execution

        Returns:
            dict(): command execution result if `log_record` is defined else None
        """
        return self._command_runner(
            command,
            log_record,
            rendered_command_code,
            rendered_command_path,
            ssh_connection,
            **kwargs,
        )

    def _command_runner(
        self,
        command,
        log_record,
        rendered_command_code,
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
            rendered_command_path (Char, optional): Rendered command path.
            ssh_connection (SSH client instance, optional): SSH connection to reuse.
            kwargs (dict):  extra arguments. Use to pass external values.
                Following keys are supported by default:
                    - "log": {values passed to logger}
                    - "key": {values passed to key parser}
        Context:
            use_sudo (Bool): use sudo for command execution

        Returns:
            dict(): command execution result if `log_record` is defined else None
        """
        if command.action == "ssh_command":
            return self._command_runner_ssh(
                log_record,
                rendered_command_code,
                rendered_command_path,
                ssh_connection,
                **kwargs,
            )
        elif command.action == "file_using_template":
            return self._command_runner_file_using_template(
                log_record,
                command.file_template_id,
                rendered_command_path,
                **kwargs,
            )
        elif command.action == "python_code":
            return self._command_runner_python_code(
                log_record,
                rendered_command_code,
                **kwargs,
            )

        error_message = _(
            "No runner found for command action '%(cmd_action)s'",
            cmd_action=command.action,
        )
        if log_record:
            log_record.finish(
                fields.Datetime.now(),
                NO_COMMAND_RUNNER_FOUND,
                None,
                error_message,
            )
        else:
            raise ValidationError(error_message)

    def _command_runner_file_using_template(
        self,
        log_record,
        file_template_id,
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
            file_template_id (recordset): The file template to use for creating
                the new file.
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
            file = file_template_id.create_file(
                server=self,
                server_dir=server_dir,
                raise_if_exists=True,
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
                        fields.Datetime.now(),
                        command_result["status"],
                        command_result["response"],
                        command_result["error"],
                    )
                else:
                    return command_result

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

            # Log the successful creation and upload of the file
            return log_record.finish(
                fields.Datetime.now(),
                0,
                _("File created and uploaded successfully"),
                None,
            )

        except Exception as e:
            # Log any exception that occurs during the process
            log_record.finish(
                fields.Datetime.now(),
                FILE_CREATION_FAILED,
                None,
                _("An error occurred: %(error)s", error=str(e)),
            )

    def _command_runner_ssh(
        self,
        log_record,
        rendered_command_code,
        rendered_command_path=None,
        ssh_connection=None,
        **kwargs,
    ):
        """Execute SSH command.
        Updates the record in the Command Log (cx.tower.command.log)

        Args:
            log_record (cx.tower.command.log()): Command log record
            rendered_command_code (Text): Rendered command code.
                We are passing in case it differs from command code in the log record.
            rendered_command_path (Char, optional): Rendered command path.
            ssh_connection (SSH client instance, optional): SSH connection to reuse.
        kwargs (dict):  extra arguments. Use to pass external values.
                Following keys are supported by default:
                    - "log": {values passed to logger}
                    - "key": {values passed to key parser}
        Context:
            use_sudo (Bool): use sudo for command execution

        Returns:
            dict(): command execution result if `log_record` is defined else None
        """
        if not ssh_connection:
            ssh_connection = self._connect(raise_on_error=False)

        # Execute command
        command_result = self._execute_command_using_ssh(
            client=ssh_connection,
            command_code=rendered_command_code,
            command_path=rendered_command_path,
            raise_on_error=False,
            sudo=self._context.get("use_sudo"),
            **kwargs,
        )

        # Log result
        if log_record:
            log_record.finish(
                fields.Datetime.now(),
                command_result["status"],
                command_result["response"],
                command_result["error"],
            )
        else:
            return command_result

    def _command_runner_python_code(
        self,
        log_record,
        rendered_code,
        **kwargs,
    ):
        """
        Execute Python code.
        Updates the record in the Command Log (cx.tower.command.log)

        Args:
            log_record (cx.tower.command.log()): Command log record
            rendered_code (Text): Rendered python code.
        kwargs (dict):  extra arguments. Use to pass external values.
                Following keys are supported by default:
                    - "log": {values passed to logger}
                    - "key": {values passed to key parser}

        Returns:
            dict(): python code execution result if `log_record` is
                    not defined else None
        """
        # Execute python code
        result = self._execute_python_code(
            code=rendered_code,
            raise_on_error=False,
            **kwargs,
        )

        # Log result
        if log_record:
            log_record.finish(
                fields.Datetime.now(),
                result["status"],
                result["response"],
                result["error"],
            )
        else:
            return result

    def _execute_command_using_ssh(
        self,
        client,
        command_code,
        command_path=None,
        raise_on_error=True,
        sudo=None,
        **kwargs,
    ):
        """This is a low level method for SSH command execution.
        Use it in case you need to get direct output of an SSH command.
        Otherwise call `execute_command()`

        Args:
            client (Connection): valid server ssh connection object
            command_code (Text): command text
            command_path (Char, optional): directory where command should be executed
            raise_on_error (bool, optional): raise error on error
            sudo (selection): use sudo Defaults to None.
            kwargs (dict):  extra arguments. Use to pass external values.
                    Following keys are supported by default:
                        - "log": {values passed to logger}
                        - "key": {values passed to key parser}

        Raises:
            ValidationError: if client is not valid
            ValidationError: command execution error

        Returns:
            dict: {
                "status": <int>,
                "response": Text,
                "error": Text
            }
        """
        if not client:
            raise ValidationError(_("SSH Client is not defined."))

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
        )

        try:
            status = []
            response = []
            error = []

            # Command is a single sting. No 'sudo' or 'sudo' w/o password
            if isinstance(prepared_command_code, str):
                status, response, error = client.exec_command(
                    prepared_command_code, sudo=sudo
                )

            # Multiple commands: sudo with password
            elif isinstance(prepared_command_code, list):
                for cmd in prepared_command_code:
                    st, resp, err = client.exec_command(cmd, sudo=sudo)
                    status.append(st)
                    response += resp
                    error += err

            # Something weird ))
            else:
                status = -1

        except Exception as e:
            if raise_on_error:
                raise ValidationError(
                    _("SSH execute command error %(err)s", err=e)
                ) from e
            else:
                status = -1
                response = []
                error = [e]

        return self._parse_ssh_command_results(
            status, response, error, secrets, **kwargs
        )

    def _execute_python_code(
        self,
        code,
        raise_on_error=True,
        **kwargs,
    ):
        """
        This is a low level method for python code execution.

        Args:
            code (Text): python code
            raise_on_error (bool, optional): raise error on error
            kwargs (dict):  extra arguments. Use to pass external values.
                    Following keys are supported by default:
                        - "log": {values passed to logger}
                        - "key": {values passed to key parser}

        Raises:
            ValidationError: python code execution error

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

        try:
            # Parse inline secrets
            code_and_secrets = self.env[
                "cx.tower.key"
            ]._parse_code_and_return_key_values(
                code, pythonic_mode=True, **kwargs.get("key", {})
            )
            command_code = code_and_secrets["code"]

            code = self.env["cx.tower.key"]._parse_code(
                command_code, pythonic_mode=True, **kwargs.get("key", {})
            )

            eval_context = self.env["cx.tower.command"]._get_eval_context(self)
            safe_eval(
                code,
                eval_context,
                mode="exec",
                nocopy=True,
            )
            result = eval_context.get("COMMAND_RESULT")
            if result:
                status = result.get("exit_code", 0)
                if status == 0:
                    response = result.get("message")
                else:
                    error = result.get("message")

        except Exception as e:
            if raise_on_error:
                raise ValidationError(
                    _("Execute python code error: %(err)s", err=e)
                ) from e
            else:
                status = PYTHON_COMMAND_ERROR
                error = e

        return {"status": status, "response": response, "error": error}

    def _prepare_ssh_command(self, command_code, path=None, sudo=None, **kwargs):
        """Prepare ssh command
        IMPORTANT:
        Commands executed with sudo will be run separately one after another
        even if there is a single command separated with '&&' or ';'
        Example:
        "pwd && ls -l" will be executed as:
            sudo pwd
            sudo ls -l

        Args:
            command_code (text): initial command
            path (str, optional): directory where command should be executed
            sudo (str, optional): sudo mode (n, p)
                n - sudo without password
                p - sudo with password
            kwargs (dict):  extra arguments. Use to pass external values.
                    Following keys are supported by default:
                        - "log": {values passed to logger}
                        - "key": {values passed to key parser}

        Returns:
            command (list|str): command splitted into separate commands
                (for sudo with password mode ('p')) or composed command
                from its parts for sudo without password mode ('n'))

        """
        # Prepare command for sudo if needed
        if sudo:
            # Add location
            sudo_prefix = "sudo -S -p ''"

            # Detect command separator
            if "&&" in command_code or ";" in command_code:
                # If command consists of several commands:
                # Replace alternative separator to avoid possible issues.
                # We need to stop always if some command issues error.
                # Check TODO above
                command_code.replace(";", "&&")
                separator = "&&"
                command_code.replace("\\", "").replace("\n", "").split(separator)
                result = (
                    command_code.replace("\\", "").replace("\n", "").split(separator)
                    if separator
                    else [command_code]
                )

                # Sudo with password expects a list of commands
                result = [f"{sudo_prefix} {cmd.strip()}" for cmd in result]

                # Merge back into a single command is sudo is without password
                if sudo == "n":
                    result = f" {separator} ".join(result)
            else:
                # Single command only
                result = f"{sudo_prefix} {command_code}"

                if sudo == "p":
                    # Sudo with password expects a list of commands
                    result = [result]

        else:
            # Command without sudo is always run as is
            result = command_code
        # Add path change command
        # TODO: we can put this command to the config level later if needed
        if path:
            # Add sudo prefix if needed
            cd_command = f"cd {path}"

            if isinstance(result, list):
                result = [cd_command] + result
            else:
                result = f"{cd_command} && {result}"

        return result

    def _parse_ssh_command_results(
        self, status, response, error, key_values=None, **kwargs
    ):
        """Parse results of the command executed with sudo.
        Paramiko returns SSH response and error as list.
        When executing command with sudo with password we return status as a list too.
        _

        Args:
            status_list (Int or list of int): Status or statuses
            response_list (list): Response
            error_list (list): Error
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
                if st != 0 and st != status:
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

        return {"status": status, "response": response, "error": error}

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

    def delete_file(self, remote_path):
        """
        Delete file from remote server

        Args:
            remote_path (Text): full path file location with file type
             (e.g. /test/my_file.txt).
        """
        self.ensure_one()
        client = self._connect(raise_on_error=False)
        client.delete_file(remote_path)

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
            # Convert string to bytes
            if isinstance(data, str):
                data = data.encode()
            file = io.BytesIO(data)
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
                _("The file %(f_path)s not found.", f_path=remote_path)
            ) from fe
        return result

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
