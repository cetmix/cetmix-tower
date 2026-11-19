# Copyright Cetmix OÜ 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase, tagged

from ..ssh.interactive_shell import MAX_RECEIVE_BYTES, InteractiveShell


class EndlessChannel:
    """Channel of a command that writes and never pauses, such as `yes`."""

    closed = False
    eof_received = False

    def recv_ready(self):
        """Always have more to give.

        Returns:
            bool: True.
        """
        return True

    def recv(self, size):
        """Return as much as it was asked for.

        Args:
            size (int): Bytes requested.

        Returns:
            bytes: That many bytes.
        """
        return b"x" * size


@tagged("post_install", "-at_install")
class TestInteractiveShell(TransactionCase):
    """The shell wrapper on its own, with no server to connect to."""

    def test_a_read_cannot_go_on_forever(self):
        """Reading stops at the limit even while the shell keeps writing.

        Without it the reader never returns to publish what it has or to
        notice that the session was asked to close.
        """
        shell = InteractiveShell(connection=None)
        shell._channel = EndlessChannel()
        output = shell.receive()
        self.assertEqual(len(output), MAX_RECEIVE_BYTES)
