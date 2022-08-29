import io
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


try:
    from paramiko import AutoAddPolicy, RSAKey, SSHClient
except ImportError:
    _logger.error(
        "import 'paramiko' error, please try to install: pip install paramiko"
    )
    AutoAddPolicy = RSAKey = SSHClient = None

try:
    from scp import SCPClient
except ImportError:
    _logger.error("import 'scp' error, please try to install: pip install scp")
    SCPClient = None


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
        self._scp = None

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
    def scp(self):
        """
        Open SCP connection to remote host.
        """
        self._scp = SCPClient(self.connection.get_transport())
        return self._scp

    def disconnect(self):
        """
        Close SSH & SCP connection.
        """
        logger = logging.getLogger("paramiko")
        if self._ssh:
            logger.info("Disconnect SSH connection")
            self._ssh.close()
        if self._scp:
            logger.info("Disconnect SCP connection")
            self._scp.close()

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

    def upload_file(self, file_path, remote_path):
        """
        Upload file to a remote directory.
        """
        self.scp.put(file_path, remote_path=remote_path, recursive=True)
        return True

    def download_file(self, file_path):
        """
        Download file from remote directory of remote host.
        """
        self.scp.get(file_path)
        return True


class CxTowerServer(models.Model):
    """Represents a server entity

    Keeps information required to connect and perform routine operations
    such as configuration, file management etc"

    """

    _name = "cx.tower.server"
    _inherit = "cx.tower.variable.mixin"
    _description = "Cetmix Tower Server"

    active = fields.Boolean(default=True)
    name = fields.Char(string="Name", required=True)
    partner_id = fields.Many2one(string="Partner", comodel_name="res.partner")
    available = fields.Boolean(
        string="Available", help="Available for operations", readonly=True
    )
    status = fields.Selection(
        string="Status",
        selection=[
            ("starting", "Starting"),
            ("running", "Running"),
            ("stopping", "Stopping"),
            ("stopped", "Stopped"),
        ],
        readonly=True,
        help="Server status",
    )
    error_code = fields.Char(string="Error Code", help="Latest operation error code")
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
    os_id = fields.Many2one(
        string="Operating System", comodel_name="cx.tower.os", required=True
    )
    tag_ids = fields.Many2many(
        comodel_name="cx.tower.tag",
        relation="cx_tower_server_tag_rel",
        column1="server_id",
        column2="tag_id",
        string="Tags",
    )
    core_count = fields.Integer(string="CPU Core Count", help="Number of CPU cores")
    ram_total = fields.Integer(string="Total RAM, Mb")
    disk_total = fields.Integer(string="Total RAM, Gb")
    note = fields.Text()

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
        command = "uname -ar"
        return command

    def _connect(self, raise_on_error=True):
        """_summary_

        Args:
            raise_on_error (bool, optional): If true will raise exception in case or error.
            Otherwise False will be returned
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
                raise ValidationError(_("SSH connection error %s" % e))
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
                        status, response, ", ".joint(error)
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

    def start(self):
        """Start servers"""
        for rec in self.filtered(lambda s: s.status == "stopped"):
            rec._connect()

    def _pre_execute_commands(self, command_ids, variables=None, sudo=None, **kwargs):
        """Will be triggered before command execution.
        Inherit to tweak command values

        Args:
            command_ids (cx.tower.object): Command recordset
            variables (dict): {command.id: [variables]}
            sudo (section): use sudo (refer to field). Defaults to None
            kwargs (dict):  extra arguments. Use to pass external values.
                Following keys are supported by default:
                    - "log": {values passed to logger}
                    - "key": {values passed to key parser}

        Returns:
            command_ids, variables, sudo
        """
        return command_ids, variables, sudo, kwargs

    def execute_commands(self, command_ids, sudo=None, **kwargs):
        """This is a main function to use for commands
            and the wrapper function for _execute commands()
        Used to execute multiple commands on multiple servers.
        This is a primary function to be used for executing commands.

        Args:
            command_ids (cx.tower.command()): Command recordset
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
        variables = command_ids.get_variables()

        # Run pre-command hook
        command_ids, variables, sudo, kwargs = self._pre_execute_commands(
            command_ids, variables, sudo, **kwargs
        )

        # Execute commands
        for server in self:
            server._execute_commands_on_server(command_ids, variables, sudo, **kwargs)

    def _execute_commands_on_server(
        self, command_ids, variables=None, sudo=None, **kwargs
    ):
        """Execute multiple commands on selected server.

        Args:
            command_ids (cx.tower.object): Command recordset
            variable (List): Variables to render the commands with
            sudo (section): use sudo (refer to field). Defaults to None.
            kwargs (dict):  extra arguments. Use for extending
        """
        self.ensure_one()
        client = self._connect(raise_on_error=False)
        log_obj = self.env["cx.tower.command.log"]
        for command_id in command_ids:

            # Get variable values for server
            variable_values = (
                self.get_variable_values(variables.get(command_id.id))
                if variables
                else False
            )

            # Render command code using variables
            if variable_values:
                rendered_code = command_id.render_code(
                    **variable_values.get(self.id)
                ).get(command_id.id)
            else:
                rendered_code = command_id.code

            # Prepare log values
            log_vals = kwargs.get("log", {})  # Get vals from kwargs
            log_vals.update({"code": rendered_code, "use_sudo": sudo})
            start_date = fields.Datetime.now()

            # Prepare key renderer values
            key_vals = kwargs.get("key", {})  # Get vals from kwargs
            key_vals.update({"server_id": self.id})
            if self.partner_id:
                key_vals.update({"partner_id": self.partner_id.id})

            # Execute command
            status, response, error = self._execute_command(
                client, rendered_code, False, sudo
            )

            # Log result
            finish_date = fields.Datetime.now()
            log_obj.record(
                self.id,
                command_id.id,
                start_date,
                finish_date,
                status,
                response,
                error,
                **log_vals
            )

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
            [status], [response], [error]
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
                for command in self._prepare_command_for_sudo(command):
                    st, resp, err = client.exec_command(command, sudo=sudo)
                    status.append(st)
                    response += resp
                    error += err
                return self._parse_sudo_command_results(status, response, error)
            else:
                result = client.exec_command(command, sudo=sudo)
        except Exception as e:
            if raise_on_error:
                raise ValidationError(_("SSH execute command error %s" % e))
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
