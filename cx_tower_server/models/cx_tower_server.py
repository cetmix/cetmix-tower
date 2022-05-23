import io

import paramiko

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, Warning as OdooWarning


class OperatingSystem(models.Model):
    _name = "cx.tower.os"
    _description = "Cetmix Tower Operating System"

    name = fields.Char(string="Name", required=True)
    parent_id = fields.Many2one(string="Previous Version", comodel_name="cx.tower.os")


class Tag(models.Model):
    _name = "cx.tower.tag"
    _description = "Cetmix Tower Tag"

    name = fields.Char(string="Name", required=True)
    server_ids = fields.Many2many(string="Servers", comodel_name="cx.tower.server")


class Server(models.Model):
    _name = "cx.tower.server"
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
    tag_ids = fields.Many2many(string="Tags", comodel_name="cx.tower.tag")
    core_count = fields.Integer(string="CPU Core Count", help="Number of CPU cores")
    ram_total = fields.Integer(string="Total RAM, Mb")
    disk_total = fields.Integer(string="Total RAM, Gb")

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

    def _get_pkey(self):
        """Get ssh key
        This function prepares and returns ssh key for the ssh connection
        Override this function to implement own password algorithms

        Returns:
            Char: password ready to be used for connection parameters
        """
        self.ensure_one()
        pkey = paramiko.RSAKey.from_private_key(io.StringIO(self.ssh_key))
        return pkey

    def _get_connection_test_command(self):
        """Get command used to test SSH connection

        Returns:
            Char: SSH command
        """
        command = "uname -ar"
        return command

    def _connect(self, raise_on_error=False):
        """_summary_

        Args:
            raise_on_error (bool, optional): If true will raise exception in case or error.
            Otherwise False will be returned
            Defaults to False.
        """

        self.ensure_one()

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            # NB: allow_agent=False is for avoiding
            # ssh-agent related connection issues~
            if self.ssh_auth_mode == "p":
                client.connect(
                    self.ip_v4_address,
                    self.ssh_port,
                    self.ssh_username,
                    self._get_password(),
                    allow_agent=False,
                )
            elif self.ssh_auth_mode == "k":
                client.connect(
                    hostname=self.ip_v4_address
                    if self.ip_v4_address
                    else self.ip_v6_address,
                    port=self.ssh_port,
                    username=self.ssh_username,
                    pkey=self._get_pkey(),
                    allow_agent=False,
                )
        except Exception as e:
            if raise_on_error:
                raise ValidationError(_("SSH connection error %s" % e))
            else:
                return False, e

        command = self._get_connection_test_command()

        res = self._execute_command(client, command=command)
        # Expecting to receive at least a single line
        if len(res["output"]) == 0:
            if raise_on_error:
                raise ValidationError(
                    _(
                        "No output received."
                        " Please log in manually and check for any issues\n"
                        "===\n%s" % res["error"]
                    )
                )
            else:
                return res["exit_code"], res["error"]
        if raise_on_error:
            raise OdooWarning(_("Connection test passed! \n%s" % res["output"]))

        return res["exit_code"], res["output"]

    def test_ssh_connection(self):
        """Test SSH connection"""
        self.ensure_one()
        self._connect(raise_on_error=True)

    def start(self):
        """Start servers"""
        for rec in self.filtered(lambda s: s.status == "stopped"):
            rec._connect()

    def _execute_command(self, client, command, sudo=False):

        # TODO: check this
        # https://stackoverflow.com/questions/22587855/running-sudo-command-with-paramiko

        feed_password = False
        if sudo and self.ssh_username != "root":
            command = "sudo -S -p '' %s" % command
            feed_password = self.ssh_password is not None and len(self.ssh_password) > 0
        stdin, stdout, stderr = client.exec_command(command)
        if feed_password:
            stdin.write(self.ssh_password + "\n")
            stdin.flush()
        return {
            "output": stdout.readlines(),
            "error": stderr.readlines(),
            "exit_code": stdout.channel.recv_exit_status(),
        }
