import io
import logging
import time

_logger = logging.getLogger(__name__)


try:
    from paramiko import (
        AutoAddPolicy,
        DSSKey,
        ECDSAKey,
        Ed25519Key,
        MissingHostKeyPolicy,
        RSAKey,
        SFTPClient,
        SSHClient,
        SSHException,
    )
except ImportError:
    _logger.error(
        "Looks like 'paramiko' is not installed, please try to "
        "install it using 'pip install paramiko'"
    )
    AutoAddPolicy = MissingHostKeyPolicy = RSAKey = SSHClient = None


class KeyLoader:
    """
    Utility for loading private SSH key in supported formats.
    """

    @staticmethod
    def load_private_key(ssh_key: str) -> RSAKey | DSSKey | ECDSAKey | Ed25519Key:
        """
        Load a private SSH key from a string.
        """
        key_file = io.StringIO(ssh_key)
        for key_class in (RSAKey, DSSKey, ECDSAKey, Ed25519Key):
            try:
                key_file.seek(0)
                return key_class.from_private_key(key_file)
            except SSHException:
                _logger.warning(
                    f"KeyLoader: failed to load key through {key_class.__name__}."
                )
        _logger.error(
            "KeyLoader: unable to load private key. "
            "Unsupported format or invalid SSH key."
        )
        raise ValueError("Unsupported format or invalid SSH key.")


class SSHConnection:
    """
    Class for managing SSH connection.
    """

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str | None = None,
        ssh_key: str | None = None,
        host_key: str | None = None,
        mode: str = "p",  # "p" for password, "k" for key
        allow_agent: bool = False,
        timeout: int = 5000,
    ):
        """
        Initialize the SSHConnection instance.
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.ssh_key = ssh_key
        self.host_key = host_key
        self.mode = mode
        self.allow_agent = allow_agent
        self.timeout = timeout
        self._ssh_client: SSHClient | None = None

    def connect(self) -> SSHClient:
        """
        Connect to the SSH server.
        """
        if self._ssh_client is not None:
            return self._ssh_client

        self._ssh_client = SSHClient()
        self._ssh_client.load_system_host_keys()

        if self.host_key:
            self._ssh_client.set_missing_host_key_policy(
                CustomHostKeyPolicy(self.host_key)
            )
        else:
            self._ssh_client.set_missing_host_key_policy(AutoAddPolicy())

        connect_params = {
            "hostname": self.host,
            "port": self.port,
            "username": self.username,
            "allow_agent": self.allow_agent,
            "timeout": self.timeout,
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

        self._ssh_client.connect(**connect_params)
        return self._ssh_client

    def disconnect(self) -> None:
        """
        Disconnect the SSH connection.
        """
        if self._ssh_client:
            _logger.info("SSHConnection: closing SSH connection.")
            self._ssh_client.close()
            self._ssh_client = None

    def get_transport(self):
        """
        Get the SSH transport.
        """
        if self._ssh_client is None:
            self.connect()
        return self._ssh_client.get_transport()


class CustomHostKeyPolicy(MissingHostKeyPolicy):
    """
    Custom SSH host key policy for validating the server's host key.

    This policy compares the server's host key (in Base64 format) with the expected key.
    If they do not match, an SSHException is raised to prevent connecting
    to an untrusted server. If they match, the key is added to the client's host keys.
    """

    def __init__(self, expected_host_key: str):
        """
        Initialize the policy with the expected host key.

        Args:
            expected_host_key (str): The expected host key in Base64 format.
        """
        self.expected_host_key = expected_host_key

    def missing_host_key(self, client, hostname, key):
        """
        Called when the SSH client receives a host key from the server
        that is not in its known hosts.

        Args:
            client: The SSH client instance.
            hostname: The hostname of the server.
            key: The host key received from the server.

        Raises:
            SSHException: If the received host key does not match the expected host key.
        """
        received_key = key.get_base64()
        if received_key != self.expected_host_key:
            raise SSHException(f"Host key mismatch for {hostname}. ")
        # If the key matches, add it to the client's known hosts
        client._host_keys.add(hostname, key.get_name(), key)


class SftpService:
    """
    Service for working with SFTP, using SSH connection.
    """

    def __init__(self, connection: SSHConnection):
        """
        Initialize the SftpService instance.
        """
        self.connection = connection
        self._sftp_client: SFTPClient | None = None

    def get_client(self) -> SFTPClient:
        """
        Get the SFTP client.
        """
        if self._sftp_client is None:
            transport = self.connection.get_transport()
            self._sftp_client = SFTPClient.from_transport(transport)
        return self._sftp_client

    def upload_file(self, file: str | io.BytesIO, remote_path: str) -> None:
        """
        Upload a file to the remote server.
        """
        client = self.get_client()
        if isinstance(file, io.BytesIO):
            client.putfo(file, remote_path)
        elif isinstance(file, str):
            client.put(file, remote_path)
        else:
            raise TypeError(f"File type {type(file).__name__} is not supported.")

    def download_file(self, remote_path: str) -> bytes:
        """
        Download a file from the remote server.
        """
        client = self.get_client()
        with client.open(remote_path, "rb") as remote_file:
            return remote_file.read()

    def delete_file(self, remote_path: str) -> None:
        """
        Delete a file from the remote server.
        """
        client = self.get_client()
        client.remove(remote_path)

    def disconnect(self) -> None:
        """
        Disconnect the SFTP client.
        """
        if self._sftp_client:
            _logger.info("SftpService: closing SFTP connection.")
            self._sftp_client.close()
            self._sftp_client = None


class CommandExecutor:
    """
    Class for executing commands on a remote server.
    """

    def __init__(self, connection: SSHConnection):
        """
        Initialize the CommandExecutor instance.
        """
        self.connection = connection

    def exec_command(
        self, command: str, sudo: str | None = None
    ) -> tuple[int, list[str], list[str]]:
        """
        Run a command on the remote server.

        Args:
            command (str): The command to execute.
            sudo (Optional[str]): Sudo mode.

        Returns:
            tuple:
                - exit_status (int)
                - stdout (list[str])
                - stderr (list[str])
        """
        ssh_client = self.connection.connect()
        use_sudo_with_password = sudo == "p" and self.connection.username != "root"

        if use_sudo_with_password and not self.connection.password:
            return 255, [], ["Sudo password not provided!"]

        try:
            stdin, stdout, stderr = ssh_client.exec_command(command)
            if use_sudo_with_password:
                stdin.write(self.connection.password + "\n")
                stdin.flush()
            exit_status = stdout.channel.recv_exit_status()
            response = stdout.readlines()
            error = stderr.readlines()
            return exit_status, response, error
        except Exception as e:
            return 255, [], [str(e)]


class SSHManager:
    """
    Facade for working with SSH connection, SFTP and command execution.
    """

    _connection_cache = {}

    def __new__(cls, connection: SSHConnection):
        """
        Create a new SSHManager instance.
        """
        key = (
            connection.host,
            connection.port,
            connection.username,
            connection.mode,
            connection.allow_agent,
            connection.password or "",
            connection.ssh_key or "",
            connection.host_key or "",
        )
        if key in cls._connection_cache:
            instance, created_at, cached_timeout = cls._connection_cache[key]
            # if timeout is changed, update the cached timeout
            if connection.timeout != cached_timeout:
                cls.delete_cache(key)
            else:
                _logger.info(
                    "Using cached SSH connection for "
                    "host=%s, port=%s, user=%s, mode=%s",
                    connection.host,
                    connection.port,
                    connection.username,
                    connection.mode,
                )
                return instance

        _logger.info(
            "Creating new SSH connection for host=%s, port=%s, user=%s, mode=%s",
            connection.host,
            connection.port,
            connection.username,
            connection.mode,
        )
        instance = super().__new__(cls)
        cls._connection_cache[key] = (instance, time.time(), connection.timeout)
        return instance

    def __init__(self, connection: SSHConnection):
        """
        Initialize the SSHManager instance.
        """
        # initialize only once
        if hasattr(self, "_initialized") and self._initialized:
            return
        self.connection = connection
        self.command_executor = CommandExecutor(connection)
        self.sftp_service = SftpService(connection)
        self._initialized = True

    @classmethod
    def delete_cache(cls, key):
        """
        Delete the cache of SSH connections.
        """
        if key in SSHManager._connection_cache:
            del SSHManager._connection_cache[key]

    def disconnect(self) -> None:
        """
        Disconnect the SSH connection and SFTP client.
        """
        if self.sftp_service._sftp_client is not None:
            self.sftp_service.disconnect()

        if self.connection._ssh_client is not None:
            self.connection.disconnect()

        key = (
            self.connection.host,
            self.connection.port,
            self.connection.username,
            self.connection.mode,
            self.connection.allow_agent,
            self.connection.password or "",
            self.connection.ssh_key or "",
            self.connection.host_key or "",
        )
        self.delete_cache(key)

    @classmethod
    def get_connection_cache(cls):
        """
        Get the connection cache.
        """
        return cls._connection_cache
