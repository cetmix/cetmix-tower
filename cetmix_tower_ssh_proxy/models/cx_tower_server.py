from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.cetmix_tower_server.ssh.ssh import SSHConnection

from ..ssh.proxy import ProxySSHManager

MAX_SSH_PROXY_HOPS = 8


class CxTowerServer(models.Model):
    _inherit = "cx.tower.server"

    ssh_connection_route = fields.Selection(
        selection=[
            ("direct", "Direct"),
            ("proxy", "SSH Proxy"),
        ],
        string="SSH Connection Route",
        compute="_compute_ssh_connection_route",
        store=True,
        readonly=False,
        default="direct",
        required=True,
        tracking=True,
        groups="cetmix_tower_base.group_manager",
        help=(
            "Direct connects to this server from the Tower host. SSH Proxy opens "
            "the target SSH connection through another Tower server using a "
            "Paramiko direct-tcpip channel."
        ),
    )
    ssh_proxy_server_id = fields.Many2one(
        comodel_name="cx.tower.server",
        string="SSH Proxy Server",
        compute="_compute_ssh_proxy_server_id",
        store=True,
        readonly=False,
        ondelete="restrict",
        tracking=True,
        groups="cetmix_tower_base.group_manager",
        help=(
            "Jump/bastion server used to reach this server. The proxy may itself "
            "use another proxy, allowing a multi-hop SSH chain."
        ),
    )

    @api.depends("ssh_connection_route")
    def _compute_ssh_proxy_server_id(self):
        """Clear the SSH proxy server when using a direct route."""
        for server in self:
            if server.ssh_connection_route == "direct":
                server.ssh_proxy_server_id = False

    @api.depends("ssh_proxy_server_id")
    def _compute_ssh_connection_route(self):
        """
        When SSH Proxy Server is set,
        SSH Connection Route must be set to Proxy
        """
        for server in self:
            if server.ssh_proxy_server_id:
                server.ssh_connection_route = "proxy"

    @api.constrains("ssh_connection_route", "ssh_proxy_server_id")
    def _check_ssh_proxy_route(self):
        """
        Validate SSH proxy configuration
        """
        for server in self:
            if server.ssh_connection_route == "direct" and server.ssh_proxy_server_id:
                raise ValidationError(
                    _(
                        "SSH Proxy Server must be empty when SSH Connection Route "
                        "is Direct."
                    )
                )

            if server.ssh_connection_route == "proxy":
                # validate the entire proxy chain to catch missing proxies,
                # circular references, archived proxies, and excessive hop depth
                server._get_ssh_route_servers()

    def _get_ssh_route_servers(self):
        """
        Return the SSH route from the outermost proxy to the target server
        """
        self.ensure_one()

        target_server = self.sudo()
        proxy_servers = target_server._get_ssh_proxy_chain()

        for proxy_server in proxy_servers:
            if not proxy_server.active:
                raise ValidationError(
                    _("SSH Proxy Server %s is archived.") % proxy_server.name
                )

        return list(reversed(proxy_servers)) + [target_server]

    def _get_ssh_route_connection_values(self, skip_host_key=False):
        """Return SSH connection values in execution order."""
        self.ensure_one()

        route_servers = self._get_ssh_route_servers()
        target_index = len(route_servers) - 1

        return [
            server._get_ssh_connection_values(
                skip_host_key=skip_host_key if index == target_index else False,
            )
            for index, server in enumerate(route_servers)
        ]

    def _get_ssh_proxy_chain(self):
        """
        Return the SSH proxy chain from the target to the outermost proxy.

        The target server itself is not included.
        """
        self.ensure_one()

        proxies = []
        visited_server_ids = {self.id}
        current_server = self

        while current_server.ssh_connection_route == "proxy":
            proxy_server = current_server.ssh_proxy_server_id

            if not proxy_server:
                raise ValidationError(
                    _("SSH Proxy Server is not configured for server %s.")
                    % current_server.name
                )

            if proxy_server.id in visited_server_ids:
                raise ValidationError(_("Circular SSH proxy route detected."))

            visited_server_ids.add(proxy_server.id)
            proxies.append(proxy_server)

            if len(proxies) > MAX_SSH_PROXY_HOPS:
                raise ValidationError(
                    _("SSH proxy route exceeds the maximum of %s hops.")
                    % MAX_SSH_PROXY_HOPS
                )

            current_server = proxy_server

        return proxies

    def _get_ssh_client(self, raise_on_error=False, timeout=5000, skip_host_key=False):
        """
        Override to return standard Tower SSH manager or a proxy-aware
        compatible manager
        """
        self.ensure_one()

        if self.sudo().ssh_connection_route != "proxy":
            return super()._get_ssh_client(
                raise_on_error=raise_on_error,
                timeout=timeout,
                skip_host_key=skip_host_key,
            )

        try:
            return self._get_ssh_proxy_manager(timeout, skip_host_key=skip_host_key)

        except Exception as error:
            if raise_on_error:
                raise ValidationError(
                    _("SSH connection error %(err)s", err=error)
                ) from error
            return False, error

    def _get_ssh_proxy_manager(self, timeout, skip_host_key=False, use_cache=True):
        """Build a verified route manager, optionally owned by one operation.

        Every hop is verified with its own host-key settings. Host-key
        discovery uses an uncached manager so that disconnecting it does not
        close a route shared with other operations.

        Args:
            timeout (int): SSH connection timeout in seconds for every hop.
            skip_host_key (bool): If True, verify the target against system
                known_hosts instead of its Tower host key. Proxy hops always
                use their own settings. Defaults to False.
            use_cache (bool): If True, reuse and cache the manager for this
                route. If False, the caller owns the manager and must
                disconnect it. Defaults to True.

        Returns:
            ProxySSHManager: Connected manager for the route.

        Raises:
            ValidationError: If the route is invalid or a hop has no host key.
            Exception: Any SSH error raised while connecting a hop, including
                an unknown or changed host key.
        """
        route_values = self.sudo()._get_ssh_route_connection_values(
            skip_host_key=skip_host_key,
        )
        connection_params = [
            {
                "host": values["host"],
                "port": values["port"],
                "username": values["username"],
                "password": values["password"],
                "ssh_key": values["ssh_key"],
                "host_key": values["host_key"],
                "mode": values["auth_mode"],
                "timeout": timeout,
            }
            for values in route_values
        ]
        return ProxySSHManager(connection_params, use_cache=use_cache)

    def _fetch_host_key(self, timeout):
        """Read the target key through verified proxy hops without target auth.

        Args:
            timeout (int): Socket and SSH handshake timeout in seconds.

        Returns:
            str: Unverified Base64 target host key for independent confirmation.

        Raises:
            ValidationError: If a proxy connection cannot be established.
            OSError: If the target cannot be reached.
            SSHException: If the target handshake fails.
        """
        server = self.sudo()
        if server.ssh_connection_route != "proxy":
            return super()._fetch_host_key(timeout)

        route = server._get_ssh_route_servers()
        proxy = route[-2]._get_ssh_proxy_manager(timeout, use_cache=False)
        try:
            sock = proxy.connection.get_transport().open_channel(
                "direct-tcpip",
                (server.ip_v4_address or server.ip_v6_address, server.ssh_port),
                ("127.0.0.1", 0),
                timeout=timeout,
            )
            return SSHConnection.fetch_host_key(
                server.ip_v4_address or server.ip_v6_address,
                server.ssh_port,
                timeout,
                sock=sock,
            )
        finally:
            proxy.disconnect()
