# Copyright Cetmix OÜ 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import codecs

from odoo.addons.cetmix_tower_server.ssh.ssh import SSHConnection

from ..constants import DEFAULT_TERMINAL_COLS, DEFAULT_TERMINAL_ROWS


class InteractiveShell:
    """Interactive pseudo terminal on top of an SSH connection."""

    def __init__(
        self,
        connection: SSHConnection,
        term: str = "xterm-256color",
        width: int = DEFAULT_TERMINAL_COLS,
        height: int = DEFAULT_TERMINAL_ROWS,
    ):
        """Store the shell settings. The channel is opened by `open`.

        Args:
            connection (SSHConnection): SSH connection to open the shell on.
            term (str): Terminal type requested from the remote host.
            width (int): Initial terminal width in columns.
            height (int): Initial terminal height in rows.
        """
        self.connection = connection
        self.term = term
        self.width = width
        self.height = height
        self._channel = None
        # Output is read in chunks that can split a multi byte character in two,
        # so the decoder has to keep the incomplete bytes between reads.
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

    def open(self):
        """Open the shell channel, or return the one already open.

        Returns:
            paramiko.Channel: Channel the shell runs on.
        """
        if self._channel is not None and not self._channel.closed:
            return self._channel

        ssh_client = self.connection.connect()
        self._channel = ssh_client.invoke_shell(
            term=self.term,
            width=self.width,
            height=self.height,
        )
        # Reads must never block: the session reads in a loop and has to stay
        # responsive to input and to close requests.
        self._channel.settimeout(0.0)
        return self._channel

    def is_active(self) -> bool:
        """Tell whether the shell can still be used.

        Returns:
            bool: True while the channel is open and the remote end has not
                closed it.
        """
        return bool(
            self._channel
            and not self._channel.closed
            and not self._channel.eof_received
        )

    def send(self, payload: str) -> int:
        """Send input to the shell.

        Args:
            payload (str): Characters to send, control characters included.

        Returns:
            int: Number of bytes sent.

        Raises:
            OSError: If the channel is closed before everything was sent.
        """
        if not payload:
            return 0
        channel = self.open()
        data = payload.encode("utf-8")
        bytes_sent = 0
        while bytes_sent < len(data):
            sent_now = channel.send(data[bytes_sent:])
            if sent_now <= 0:
                raise OSError("SSH channel closed while sending terminal input.")
            bytes_sent += sent_now
        return bytes_sent

    def resize(self, width: int, height: int):
        """Resize the remote pseudo terminal.

        Args:
            width (int): New terminal width in columns.
            height (int): New terminal height in rows.
        """
        channel = self.open()
        channel.resize_pty(width=width, height=height)
        self.width = width
        self.height = height

    def receive(self, chunk_size: int = 65535) -> str:
        """Read everything the shell has produced so far.

        Args:
            chunk_size (int): Maximum number of bytes read per call.

        Returns:
            str: Decoded output, empty string when nothing is available.
        """
        channel = self.open()
        chunks = []
        while channel.recv_ready():
            chunks.append(channel.recv(chunk_size))
        if not chunks:
            return ""
        return self._decoder.decode(b"".join(chunks))

    def close(self):
        """Close the shell channel."""
        if self._channel is not None:
            try:
                if not self._channel.closed:
                    self._channel.close()
            finally:
                self._channel = None
