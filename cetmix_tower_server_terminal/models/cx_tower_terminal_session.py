# Copyright Cetmix OÜ 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json
import logging
import uuid

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import SQL

from odoo.addons.bus.models.bus import ODOO_NOTIFY_FUNCTION

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
    NOTIFY_CHANNEL,
    STATE_CLOSED,
    STATE_NEW,
    STATE_OPEN,
    STATE_SELECTION,
    USER_DISCONNECTED_MESSAGE,
)

_logger = logging.getLogger(__name__)

TERMINAL_ACTION_TAG = "cetmix_tower_server_terminal.terminal"


class CxTowerTerminalSession(models.TransientModel):
    """Terminal session of one user on one server.

    The record is what the browser and the Odoo processes agree on: it holds the
    token the session is addressed with and the state the user sees. The shell
    itself lives in the process that serves the websocket of the browser, see
    `tools/terminal_registry.py`.
    """

    _name = "cx.tower.terminal.session"
    _description = "Cetmix Tower Terminal Session"
    _transient_max_hours = 12

    name = fields.Char(required=True, readonly=True)
    session_token = fields.Char(
        required=True,
        readonly=True,
        copy=False,
        index=True,
        default=lambda self: self._default_session_token(),
        help="Addresses the session and names the bus channel it publishes to."
        " Must stay secret: whoever knows it can read the terminal output.",
    )
    server_id = fields.Many2one(
        comodel_name="cx.tower.server",
        required=True,
        readonly=True,
        # A session is meaningless without its server, and being transient it
        # must never be the reason a server cannot be deleted.
        ondelete="cascade",
    )
    state = fields.Selection(
        selection=lambda self: self._selection_state(),
        default=lambda self: self._default_state(),
        required=True,
        readonly=True,
    )
    message = fields.Char(readonly=True)

    # -- access

    @api.constrains("server_id")
    def _check_server_access(self):
        """Let a session be created only on a server the user can read.

        The shell is opened with the credentials of the server, read with
        `sudo()`, so the right to use that server cannot be checked only in the
        action that creates the session: a user who may create a record could
        otherwise name a server they are not allowed to see.
        """
        for session in self:
            session.server_id.check_access("read")

    # -- defaults and selections

    @api.model
    def _default_session_token(self):
        """Return a new session token.

        Returns:
            str: Random token, unguessable by design.
        """
        return uuid.uuid4().hex

    @api.model
    def _selection_state(self):
        """Return the states a session can be in.

        Returns:
            list: Selection list of (value, label) tuples.
        """
        return STATE_SELECTION

    @api.model
    def _default_state(self):
        """Return the state a session starts in.

        A session is only `open` once its shell has actually been opened, which
        happens when the browser subscribes to its channel. Until then there is
        nothing to talk to.

        Returns:
            str: Default state value.
        """
        return STATE_NEW

    # -- opening a session

    @api.model
    def action_open_for_server(self, server_id):
        """Create a session on a server and return the action that renders it.

        Args:
            server_id (int): Id of the `cx.tower.server` to connect to.

        Returns:
            dict: Client action that opens the terminal.

        Raises:
            ValidationError: If the server does not exist.
        """
        server = self.env["cx.tower.server"].browse(server_id).exists()
        if not server:
            raise ValidationError(self.env._("Server not found."))
        server.check_access("read")
        session = self.create(
            {
                "name": self.env._("Terminal: %(server)s", server=server.name),
                "server_id": server.id,
            }
        )
        _logger.info(
            "Terminal: session %s opened on server %s by user %s",
            session.id,
            server.name,
            self.env.user.login,
        )
        return session._get_client_action()

    def _get_client_action(self):
        """Return the client action that renders this session.

        Returns:
            dict: `ir.actions.client` describing the terminal.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": TERMINAL_ACTION_TAG,
            "name": self.name,
            "params": self._get_client_params(),
        }

    def _get_bus_channel(self):
        """Return the bus channel this session publishes its output to.

        Returns:
            str: Channel name. It contains the session token, which is what
                makes it unguessable, as `bus.bus._sendone` requires.
        """
        self.ensure_one()
        return f"{BUS_CHANNEL_PREFIX}{self.session_token}"

    def _get_client_params(self):
        """Return everything the client needs to talk to this session.

        Returns:
            dict: Session id, token, bus channel, title, server name and the
                user and host the shell runs as, which is what a terminal shows.
        """
        self.ensure_one()
        server = self.server_id
        host = server.ip_v4_address or server.ip_v6_address or server.name
        return {
            "session_id": self.id,
            "session_token": self.session_token,
            "bus_channel": self._get_bus_channel(),
            "title": self.name,
            "server_name": server.name,
            "target": f"{server.ssh_username}@{host}",
        }

    # -- validation

    def _sanitize_terminal_size(self, cols, rows):
        """Keep the size sent by the browser within the allowed bounds.

        Args:
            cols (int): Number of columns asked for.
            rows (int): Number of rows asked for.

        Returns:
            tuple: Sanitized (cols, rows).

        Raises:
            ValidationError: If the size is not made of numbers.
        """
        try:
            cols, rows = int(cols), int(rows)
        except (TypeError, ValueError) as error:
            raise ValidationError(self.env._("Invalid terminal size.")) from error
        return (
            min(max(cols, MIN_TERMINAL_COLS), MAX_TERMINAL_COLS),
            min(max(rows, MIN_TERMINAL_ROWS), MAX_TERMINAL_ROWS),
        )

    # -- talking to the process that owns the session

    def _notify_owner(self, action, payload=None):
        """Send an action to the process the shell of this session runs in.

        The shell lives in the process that serves the websocket of the browser,
        which is rarely the one serving this request, so the action travels as a
        postgres notification. It is delivered on commit to every process
        listening on this database: the one holding the session runs it, the
        others do not know the token and ignore it. `bus.bus` reaches this
        process the same way, see `bus.bus._ensure_hooks`.

        Args:
            action (str): Action to run, one of the `ACTION_*` constants.
            payload (dict): Extra keys to send along with the action.
        """
        self.ensure_one()
        message = dict(payload or {}, token=self.session_token, action=action)
        self.env.cr.execute(
            SQL(
                "SELECT %s(%s, %s)",
                SQL.identifier(ODOO_NOTIFY_FUNCTION),
                NOTIFY_CHANNEL,
                json.dumps(message),
            )
        )

    def _split_input(self, payload):
        """Cut input into pieces that fit in a postgres notification.

        Json escaping can turn one character into twelve bytes, so the limit
        has to be measured on what is actually sent, not on the text.

        Args:
            payload (str): Characters typed in the browser.

        Returns:
            list: Pieces of the payload, in the order they were typed.
        """
        self.ensure_one()
        if len(json.dumps(payload)) <= MAX_NOTIFY_BYTES:
            return [payload]
        # The size starts at the two quotes the encoded string is wrapped in,
        # and each character costs what it takes once escaped.
        pieces, piece, size = [], [], 2
        for character in payload:
            cost = len(json.dumps(character)) - 2
            if size + cost > MAX_NOTIFY_BYTES:
                pieces.append("".join(piece))
                piece, size = [], 2
            piece.append(character)
            size += cost
        if piece:
            pieces.append("".join(piece))
        return pieces

    def terminal_send(self, payload):
        """Send what the user typed to the shell.

        Output is not returned here: it is published on the bus channel of the
        session as soon as the shell produces it.

        Args:
            payload (str): Characters typed in the browser.

        Returns:
            bool: True if the input was forwarded, False if the session ended.

        Raises:
            ValidationError: If the input is not a string or is too large.
        """
        self.ensure_one()
        self.check_access("write")
        if not isinstance(payload, str):
            raise ValidationError(self.env._("Invalid terminal input."))
        if len(payload) > MAX_INPUT_LENGTH:
            raise ValidationError(self.env._("Terminal input is too large."))
        if self.state != STATE_OPEN:
            return False
        for piece in self._split_input(payload):
            self._notify_owner(ACTION_INPUT, {"data": piece})
        return True

    def terminal_resize(self, cols, rows):
        """Resize the remote pseudo terminal to the size of the browser window.

        Args:
            cols (int): Number of columns.
            rows (int): Number of rows.

        Returns:
            bool: True if the new size was forwarded, False if the session ended.
        """
        self.ensure_one()
        self.check_access("write")
        cols, rows = self._sanitize_terminal_size(cols, rows)
        if self.state != STATE_OPEN:
            return False
        self._notify_owner(ACTION_RESIZE, {"cols": cols, "rows": rows})
        return True

    def terminal_close(self):
        """Close the session.

        Returns:
            bool: True once the session is marked as closed.
        """
        self.ensure_one()
        self.check_access("write")
        message = str(USER_DISCONNECTED_MESSAGE)
        if self.state in (STATE_NEW, STATE_OPEN):
            self._notify_owner(ACTION_CLOSE, {"message": message})
        self.write({"state": STATE_CLOSED, "message": message})
        return True

    def terminal_reconnect(self):
        """Close this session and open a new one on the same server.

        A shell cannot be revived: once its process is gone, or the session was
        closed, the only way back is a new session.

        Returns:
            dict: Client parameters of the new session.
        """
        self.ensure_one()
        self.check_access("write")
        server = self.server_id
        self.terminal_close()
        session = self.create({"name": self.name, "server_id": server.id})
        return session._get_client_params()

    def unlink(self):
        """Close the shells of the sessions being deleted.

        Returns:
            bool: True if the records were deleted.
        """
        for session in self:
            if session.state in (STATE_NEW, STATE_OPEN):
                session._notify_owner(ACTION_CLOSE)
        return super().unlink()
