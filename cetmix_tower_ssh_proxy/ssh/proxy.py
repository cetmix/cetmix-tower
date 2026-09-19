import logging
import time

from odoo.addons.cetmix_tower_server.ssh.ssh import (
    AutoAddPolicy,
    CommandExecutor,
    CustomHostKeyPolicy,
    KeyLoader,
    SftpService,
    SSHClient,
    SSHConnection,
)

_logger = logging.getLogger(__name__)


class ProxySSHConnection(SSHConnection):
    """
    SSH connection established through an existing Paramiko channel
    """

    def __init__(self, *args, sock=None, **kwargs):
        """
        Initialize the proxy SSH connection.
        """
        super().__init__(*args, **kwargs)
        self.sock = sock

    def connect(self) -> SSHClient:
        """
        Connect to the SSH server through the configured Paramiko channel.
        """
        if self._ssh_client is not None:
            return self._ssh_client

        ssh_client = SSHClient()
        try:
            ssh_client.load_system_host_keys()

            if self.host_key:
                ssh_client.set_missing_host_key_policy(
                    CustomHostKeyPolicy(self.host_key)
                )
            else:
                ssh_client.set_missing_host_key_policy(AutoAddPolicy())

            connect_params = {
                "hostname": self.host,
                "port": self.port,
                "username": self.username,
                "allow_agent": self.allow_agent,
                "timeout": self.timeout,
                "sock": self.sock,
            }

            if self.mode == "p":
                if not self.password:
                    raise ValueError("For password mode, you need to pass a password.")
                connect_params["password"] = self.password
            elif self.mode == "k":
                if not self.ssh_key:
                    raise ValueError("For key mode, you need to pass an SSH key.")
                connect_params["pkey"] = KeyLoader.load_private_key(self.ssh_key)
            else:
                raise ValueError(f"Unsupported connection mode: {self.mode}")

            ssh_client.connect(**connect_params)
        except Exception:
            ssh_client.close()

            if self.sock is not None:
                try:
                    self.sock.close()
                finally:
                    self.sock = None

            raise

        self._ssh_client = ssh_client
        return self._ssh_client

    def disconnect(self) -> None:  # pylint: disable=missing-return
        """
        Disconnect the SSH connection and close the proxy channel
        """
        try:
            return super().disconnect()
        finally:
            if self.sock is not None:
                try:
                    self.sock.close()
                finally:
                    self.sock = None


class ProxySSHManager:
    """
    Facade for managing SSH connections through proxy servers
    """

    _connection_cache = {}

    def __new__(cls, connection_params):
        """
        Create or reuse a ProxySSHManager instance for the SSH route
        """
        key = cls._get_cache_key(connection_params)
        timeout = connection_params[0]["timeout"]

        route_message = " -> ".join(
            f"{params['host']}:{params['port']}" for params in connection_params
        )

        if key in cls._connection_cache:
            instance, _, cached_timeout = cls._connection_cache[key]

            if timeout != cached_timeout:
                instance.disconnect()
            else:
                _logger.info(
                    "Using cached SSH proxy connection for route=%s",
                    route_message,
                )
                return instance

        _logger.info(
            "Creating new SSH proxy connection for route=%s",
            route_message,
        )

        return super().__new__(cls)

    def __init__(self, connection_params):
        """
        Initialize the proxy SSH route and target services.
        """
        # Initialize only once.
        if hasattr(self, "_initialized") and self._initialized:
            return

        self.proxy_connections = []
        self.connection = None
        self._cache_key = self._get_cache_key(connection_params)
        self._cached_timeout = connection_params[0]["timeout"]

        try:
            self.connection = self._build_connections(connection_params)

            # Ensure the complete proxy route, including the target SSH
            # connection, is valid before caching the manager.
            self.connection.connect()

            self.command_executor = CommandExecutor(self.connection)
            self.sftp_service = SftpService(self.connection)
            self._initialized = True

            # Cache only a fully initialized manager.
            self._connection_cache[self._cache_key] = (
                self,
                time.time(),
                self._cached_timeout,
            )
        except Exception:
            self._disconnect_connections()
            raise

    @staticmethod
    def _get_connection_cache_key(params):
        """
        Return the cache key for a single SSH connection in the route.
        """
        return (
            params["host"],
            params["port"],
            params["username"],
            params["mode"],
            params.get("allow_agent", False),
            params.get("password") or "",
            params.get("ssh_key") or "",
            params.get("host_key") or "",
        )

    @classmethod
    def _get_cache_key(cls, connection_params):
        """
        Return the cache key for the complete SSH proxy route.
        """
        return tuple(
            cls._get_connection_cache_key(params) for params in connection_params
        )

    def _build_connections(self, connection_params):
        """
        Build the SSH proxy route and return the target connection.
        """
        previous_connection = None

        for index, params in enumerate(connection_params):
            params = params.copy()

            if previous_connection is None:
                connection = SSHConnection(**params)
            else:
                transport = previous_connection.get_transport()
                sock = transport.open_channel(
                    "direct-tcpip",
                    (params["host"], params["port"]),
                    ("127.0.0.1", 0),
                )
                try:
                    connection = ProxySSHConnection(
                        **params,
                        sock=sock,
                    )
                except Exception:
                    sock.close()
                    raise

            if index < len(connection_params) - 1:
                self.proxy_connections.append(connection)

            previous_connection = connection

        return previous_connection

    def _disconnect_connections(self) -> None:
        """
        Disconnect the target and all proxy-hop connections.
        """
        if self.connection is not None:
            try:
                self.connection.disconnect()
            except Exception:
                _logger.exception("Failed to disconnect target SSH connection.")

        for connection in reversed(self.proxy_connections):
            try:
                connection.disconnect()
            except Exception:
                _logger.exception("Failed to disconnect SSH proxy connection.")

    @classmethod
    def delete_cache(cls, key):
        """
        Delete the cached SSH proxy manager for the route.
        """
        if key in cls._connection_cache:
            del cls._connection_cache[key]

    def disconnect(self) -> None:
        """
        Disconnect SFTP, target and proxy connections and clear the cache.
        """
        try:
            if self.sftp_service._sftp_client is not None:
                try:
                    self.sftp_service.disconnect()
                except Exception:
                    _logger.exception("Failed to disconnect SFTP client.")
        finally:
            try:
                self._disconnect_connections()
            finally:
                self.delete_cache(self._cache_key)

    @classmethod
    def get_connection_cache(cls):
        """
        Get the SSH proxy connection cache.
        """
        return cls._connection_cache
