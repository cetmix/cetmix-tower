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
        # ssh_key = RSAKey.from_private_key_file(self.ssh_key_filepath)
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

    def exec_command(self, command, sudo=False):
        """
        Execute command in remove SSH
        """
        feed_password = False
        # TODO: check this
        # https://stackoverflow.com/questions/22587855/running-sudo-command-with-paramiko
        if sudo and self.username != "root":
            command = "sudo -S -p '' %s" % command
            feed_password = bool(self.password)

        stdin, stdout, stderr = self.connection.exec_command(command)
        if feed_password:
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
    ssh_key = fields.Text(string="SSH Private Key")
    ssh_auth_mode = fields.Selection(
        string="SSH Auth Mode",
        selection=[
            ("p", "Password"),
            ("k", "Key"),
        ],
        default="p",
        required=True,
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
            if rec.ssh_auth_mode == "k" and not rec.ssh_key:
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
                ssh_key=self.ssh_key,
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

    def _execute_command(self, client, command, sudo=False, raise_on_error=True):
        """
        Execute command method: can be overridden
        """
        if not client:
            raise ValidationError(_("SSH Client is not defined."))
        try:
            result = client.exec_command(command, sudo=sudo)
        except Exception as e:
            if raise_on_error:
                raise ValidationError(_("SSH execute command error %s" % e))
            else:
                return False, e
        return result

    def action_execute_command(self):
        """
        Return wizard action to select command and execute it
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
