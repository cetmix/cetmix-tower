# Copyright Cetmix OÜ 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import codecs
import time

from odoo.addons.cetmix_tower_server.ssh.ssh import SSHConnection

from ..constants import DEFAULT_TERMINAL_COLS, DEFAULT_TERMINAL_ROWS

# Seconds spent trying to hand input over to a shell that is not reading it
SEND_TIMEOUT = 5
# Seconds between attempts while the remote window is full
SEND_RETRY_SLEEP = 0.02
# Maximum bytes read in one pass, so a command that never stops writing cannot
# keep the reader from publishing what it already has
MAX_RECEIVE_BYTES = 256 * 1024


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

        The channel does not block, so a remote window that is momentarily full
        raises instead of waiting. That is back pressure, not a broken session:
        it is retried for a while before giving up.

        Args:
            payload (str): Characters to send, control characters included.

        Returns:
            int: Number of bytes sent.

        Raises:
            OSError: If the channel is closed, or stays unable to take the
                input for longer than SEND_TIMEOUT.
        """
        if not payload:
            return 0
        channel = self.open()
        data = payload.encode("utf-8")
        bytes_sent = 0
        deadline = time.monotonic() + SEND_TIMEOUT
        while bytes_sent < len(data):
            try:
                sent_now = channel.send(data[bytes_sent:])
            except TimeoutError as error:
                if time.monotonic() > deadline:
                    raise OSError(
                        "The remote shell stopped accepting input."
                    ) from error
                time.sleep(SEND_RETRY_SLEEP)
                continue
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
