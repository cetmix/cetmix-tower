# Copyright Cetmix OÜ 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from ..constants import (
    ACTION_CLOSE,
    ACTION_INPUT,
    ACTION_RESIZE,
    BUS_CHANNEL_PREFIX,
    MAX_INPUT_LENGTH,
    MAX_NOTIFY_BYTES,
    MAX_TERMINAL_COLS,
    MAX_TERMINAL_ROWS,
    MIN_TERMINAL_COLS,
    MIN_TERMINAL_ROWS,
    STATE_CLOSED,
    STATE_NEW,
)
from .common import TestTowerTerminalCommon


@tagged("post_install", "-at_install")
class TestTerminalSession(TestTowerTerminalCommon):
    """What the browser can ask the session record to do."""

    def test_open_for_server_returns_client_action(self):
        """Opening a terminal creates a session and returns its client action."""
        action = self.TerminalSession.action_open_for_server(self.server_test_1.id)
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "cetmix_tower_server_terminal.terminal")

        session = self.TerminalSession.browse(action["params"]["session_id"])
        self.assertEqual(session.server_id, self.server_test_1)
        self.assertEqual(
            session.state,
            STATE_NEW,
            "A session is only open once its shell has been opened",
        )
        self.assertIn(self.server_test_1.name, session.name)
        self.assertEqual(
            action["params"]["bus_channel"],
            f"{BUS_CHANNEL_PREFIX}{session.session_token}",
            "The client must listen to the channel named after the token",
        )

    def test_open_for_server_unknown_server(self):
        """Opening a terminal on a server that does not exist is refused."""
        with self.assertRaises(ValidationError):
            self.TerminalSession.action_open_for_server(0)

    def test_sessions_do_not_share_tokens(self):
        """Every session gets its own token."""
        first = self.open_session()
        second = self.open_session()
        self.assertNotEqual(first.session_token, second.session_token)

    def test_sanitize_terminal_size(self):
        """A size out of bounds is clamped, a size that is not a number is refused."""
        session = self.open_session()
        self.assertEqual(
            session._sanitize_terminal_size(120, 40),
            (120, 40),
            "A usable size must be left alone",
        )
        self.assertEqual(
            session._sanitize_terminal_size(1, 1),
            (MIN_TERMINAL_COLS, MIN_TERMINAL_ROWS),
        )
        self.assertEqual(
            session._sanitize_terminal_size(99999, 99999),
            (MAX_TERMINAL_COLS, MAX_TERMINAL_ROWS),
        )
        with self.assertRaises(ValidationError):
            session._sanitize_terminal_size("wide", 40)

    def test_send_input_is_forwarded(self):
        """Input reaches the process that owns the shell."""
        session = self.mark_open(self.open_session())
        with self.capture_notifications(session) as sent:
            self.assertTrue(session.terminal_send("ls -la\n"))
        self.assertEqual(sent, [(ACTION_INPUT, {"data": "ls -la\n"})])

    def test_plain_input_travels_in_one_notification(self):
        """Ordinary input is not split for nothing."""
        session = self.mark_open(self.open_session())
        self.assertEqual(session._split_input("ls -la\n"), ["ls -la\n"])

    def test_input_too_large_for_a_notification_is_split(self):
        """Json escaping is what decides the size, not the number of characters.

        A thousand emoji are a thousand characters and twelve thousand bytes
        once encoded, well over what postgres accepts in a notification.
        """
        session = self.mark_open(self.open_session())
        payload = "🙂" * 1000
        pieces = session._split_input(payload)
        self.assertGreater(len(pieces), 1, "Such a payload has to be split")
        self.assertEqual("".join(pieces), payload, "Nothing may be lost or moved")
        for piece in pieces:
            self.assertLessEqual(
                len(json.dumps(piece)),
                MAX_NOTIFY_BYTES,
                "Every piece has to fit in a notification",
            )

    def test_large_input_is_sent_in_order(self):
        """The pieces of a split payload reach the shell as they were typed."""
        session = self.mark_open(self.open_session())
        payload = "🙂" * 1000
        with self.capture_notifications(session) as sent:
            self.assertTrue(session.terminal_send(payload))
        self.assertGreater(len(sent), 1, "Such a payload has to be split")
        self.assertEqual([action for action, _data in sent], [ACTION_INPUT] * len(sent))
        self.assertEqual(
            "".join(data["data"] for _action, data in sent),
            payload,
            "The shell has to receive exactly what was typed, in order",
        )

    def test_send_input_validation(self):
        """Input that is not a reasonably sized string is refused."""
        session = self.mark_open(self.open_session())
        with self.assertRaises(ValidationError):
            session.terminal_send(42)
        with self.assertRaises(ValidationError):
            session.terminal_send("x" * (MAX_INPUT_LENGTH + 1))

    def test_send_input_while_connecting(self):
        """A session whose shell is not up yet takes no input."""
        session = self.open_session()
        with self.capture_notifications(session) as sent:
            self.assertFalse(session.terminal_send("ls\n"))
        self.assertEqual(sent, [], "There is no shell to send anything to yet")

    def test_send_input_to_closed_session(self):
        """A closed session takes no input and says so."""
        session = self.mark_open(self.open_session())
        session.terminal_close()
        with self.capture_notifications(session) as sent:
            self.assertFalse(session.terminal_send("ls\n"))
        self.assertEqual(sent, [], "A closed session must not reach the shell")

    def test_resize_is_sanitized_and_forwarded(self):
        """The size asked for by the browser is clamped before it is forwarded."""
        session = self.mark_open(self.open_session())
        with self.capture_notifications(session) as sent:
            self.assertTrue(session.terminal_resize(99999, 10))
        self.assertEqual(
            sent, [(ACTION_RESIZE, {"cols": MAX_TERMINAL_COLS, "rows": 10})]
        )

    def test_resize_closed_session(self):
        """A closed session is not resized."""
        session = self.mark_open(self.open_session())
        session.terminal_close()
        self.assertFalse(session.terminal_resize(100, 40))

    def test_close_marks_the_session_and_notifies_once(self):
        """Closing writes the state and asks the owner to close the shell."""
        session = self.mark_open(self.open_session())
        with self.capture_notifications(session) as sent:
            session.terminal_close()
        self.assertEqual(session.state, STATE_CLOSED)
        self.assertTrue(session.message)
        self.assertEqual([action for action, _payload in sent], [ACTION_CLOSE])

        with self.capture_notifications(session) as sent:
            session.terminal_close()
        self.assertEqual(sent, [], "A session is only closed once")

    def test_close_runs_a_real_notification(self):
        """The notification sent to the owner is valid sql."""
        session = self.mark_open(self.open_session())
        session.terminal_close()
        self.assertEqual(session.state, STATE_CLOSED)

    def test_reconnect_opens_a_new_session(self):
        """Reconnecting closes the old session and hands out a new one."""
        session = self.mark_open(self.open_session())
        params = session.terminal_reconnect()
        new_session = self.TerminalSession.browse(params["session_id"])
        self.assertEqual(session.state, STATE_CLOSED)
        self.assertNotEqual(new_session, session)
        self.assertEqual(new_session.state, STATE_NEW)
        self.assertEqual(new_session.server_id, self.server_test_1)
        self.assertEqual(
            params["bus_channel"],
            f"{BUS_CHANNEL_PREFIX}{new_session.session_token}",
        )

    def test_unlink_closes_an_open_session(self):
        """Deleting a session closes the shell behind it."""
        session = self.mark_open(self.open_session())
        with self.capture_notifications(session) as sent:
            session.unlink()
        self.assertEqual(sent, [(ACTION_CLOSE, None)])

    def test_unlink_closed_session(self):
        """Deleting a session that already ended notifies nobody."""
        session = self.mark_open(self.open_session())
        session.terminal_close()
        with self.capture_notifications(session) as sent:
            session.unlink()
        self.assertEqual(sent, [], "There is no shell left to close")
