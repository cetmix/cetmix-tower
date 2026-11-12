# Copyright Cetmix OÜ 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from contextlib import contextmanager
from unittest.mock import patch

from odoo.addons.cetmix_tower_server.tests.common import TestTowerCommon

from ..constants import STATE_OPEN


class FakeShell:
    """Interactive shell that records what it was asked to do.

    Lets the session be tested without a server to connect to.
    """

    def __init__(self, output=""):
        """Set up the shell.

        Args:
            output (str): Output returned by the first `receive` call.
        """
        self.sent = []
        self.size = None
        self.closed = False
        self.active = True
        self.output = output
        self.send_error = None

    def is_active(self):
        """Tell whether the shell is still usable.

        Returns:
            bool: True while the fake shell is active.
        """
        return self.active

    def send(self, payload):
        """Record input, or raise what the test asked for.

        Args:
            payload (str): Input to record.

        Returns:
            int: Number of characters recorded.

        Raises:
            Exception: Whatever was set in `send_error`.
        """
        if self.send_error:
            raise self.send_error
        self.sent.append(payload)
        return len(payload)

    def resize(self, width, height):
        """Record the requested size.

        Args:
            width (int): Number of columns.
            height (int): Number of rows.
        """
        self.size = (width, height)

    def receive(self, chunk_size=65535):
        """Return the pending output once.

        Args:
            chunk_size (int): Ignored, kept to match the real shell.

        Returns:
            str: Pending output, empty from the second call on.
        """
        output, self.output = self.output, ""
        return output

    def close(self):
        """Mark the shell as closed."""
        self.closed = True
        self.active = False


class TestTowerTerminalCommon(TestTowerCommon):
    """Common setup for the terminal tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.TerminalSession = cls.env["cx.tower.terminal.session"]
        # Managers only see the servers they manage
        cls.server_test_1.write({"manager_ids": [(4, cls.manager.id)]})

    def mark_open(self, session):
        """Mark a session as connected, the way its shell does when it opens.

        Args:
            session (odoo.model.Model): Session to mark.

        Returns:
            odoo.model.Model: The same session.
        """
        session.sudo().write({"state": STATE_OPEN})
        return session

    @contextmanager
    def capture_notifications(self, session):
        """Record what the session sends to the process that owns its shell.

        A plain function is used instead of a mock because `unlink` reads
        `_ondelete` on every method of the model, and a mock answers that it has
        one, which makes Odoo call it as if it were an `@api.ondelete` hook.

        Args:
            session (odoo.model.Model): Session whose model is watched.

        Yields:
            list: Tuples of (action, payload), in the order they were sent.
        """
        sent = []

        def notify_owner(record, action, payload=None):
            sent.append((action, payload))

        with patch.object(type(session), "_notify_owner", notify_owner):
            yield sent

    def open_session(self, user=None, server=None):
        """Create a terminal session the way the server button does.

        Args:
            user (odoo.model.Model): User to act as, the current one by default.
            server (odoo.model.Model): Server to connect to, `server_test_1` by
                default.

        Returns:
            odoo.model.Model: The created `cx.tower.terminal.session` record.
        """
        server = server or self.server_test_1
        sessions = self.TerminalSession
        if user:
            sessions = sessions.with_user(user)
            server = server.with_user(user)
        action = sessions.action_open_for_server(server.id)
        return sessions.browse(action["params"]["session_id"])
