# Copyright Cetmix OÜ 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from cetmix_tower_server.ssh.ssh import SSHConnection


class InteractiveShell:
    """Interactive PTY shell over SSH."""

    def __init__(
        self,
        connection: SSHConnection,
        term: str = "xterm",
        width: int = 160,
        height: int = 48,
    ):
        """Initialize the interactive shell with connection parameters.

        Args:
            connection (SSHConnection): Active SSH connection to wrap.
            term (str): Terminal type string to request from the server.
            width (int): Initial terminal width in columns.
            height (int): Initial terminal height in rows.
        """
        self.connection = connection
        self.term = term
        self.width = width
        self.height = height
        self._channel = None

    def open(self):
        """Open the interactive shell channel.

        Returns:
            paramiko.Channel: The active shell channel.
        """
        if self._channel is not None and not self._channel.closed:
            return self._channel

        ssh_client = self.connection.connect()
        self._channel = ssh_client.invoke_shell(
            term=self.term,
            width=self.width,
            height=self.height,
        )
        self._channel.settimeout(0.0)
        return self._channel

    def is_active(self) -> bool:
        """Check whether the shell channel is still active.

        Returns:
            bool: True if the channel exists, is open, and has not received EOF.
        """
        return bool(
            self._channel
            and not self._channel.closed
            and not self._channel.eof_received
        )

    def send(self, payload: str) -> int:
        """Send data to the shell channel.

        Args:
            payload (str): Text or control characters to transmit.

        Returns:
            int: Total number of bytes sent.
        """
        if not payload:
            return 0
        channel = self.open()
        bytes_sent = 0
        while bytes_sent < len(payload):
            sent_now = channel.send(payload[bytes_sent:])
            if sent_now <= 0:
                raise OSError("SSH channel closed while sending terminal payload.")
            bytes_sent += sent_now
        return bytes_sent

    def resize(self, width: int, height: int):
        """Resize the remote PTY to match the visible terminal size.

        Args:
            width (int): New terminal width in columns.
            height (int): New terminal height in rows.
        """
        channel = self.open()
        channel.resize_pty(width=width, height=height)
        self.width = width
        self.height = height

    def receive(self, chunk_size: int = 65535) -> str:
        """Read all currently available bytes from the shell channel.

        Args:
            chunk_size (int): Maximum bytes to read in each recv() call.

        Returns:
            str: Decoded output string; empty string if no data is ready.
        """
        channel = self.open()
        chunks = []
        while channel.recv_ready():
            chunks.append(channel.recv(chunk_size))
        return b"".join(chunks).decode("utf-8", errors="replace")

    def close(self):
        """Close the shell channel."""
        if self._channel is not None:
            try:
                if not self._channel.closed:
                    self._channel.close()
            finally:
                self._channel = None
