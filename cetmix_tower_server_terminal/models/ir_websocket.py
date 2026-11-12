# Copyright Cetmix OÜ 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import models
from odoo.http import request

from odoo.addons.bus.websocket import Websocket, wsrequest

from ..constants import BUS_CHANNEL_PREFIX, STATE_NEW
from ..tools.terminal_registry import (
    detach_websocket,
    ensure_session,
    sync_websocket,
)

_logger = logging.getLogger(__name__)


class IrWebsocket(models.AbstractModel):
    _inherit = "ir.websocket"

    def _build_bus_channel_list(self, channels):
        """Start the terminal sessions whose output channel is subscribed to.

        This runs in the process that serves the websocket of the browser, which
        is the only process a terminal session can live in: it is the one the
        browser keeps a connection to for as long as the terminal is open.

        Args:
            channels (list): Channels the client asked to subscribe to.

        Returns:
            list: Channels to subscribe the client to.
        """
        tokens = [
            channel[len(BUS_CHANNEL_PREFIX) :]
            for channel in channels
            if isinstance(channel, str) and channel.startswith(BUS_CHANNEL_PREFIX)
        ]
        # `request` is set when the channel list is built for an http request
        # instead of a websocket. There is no websocket to tie a session to
        # then, so there is nothing to do here.
        if not request:
            sync_websocket(wsrequest.ws, tokens)
            if tokens:
                self._start_terminal_sessions(tokens)
        return super()._build_bus_channel_list(channels)

    def _start_terminal_sessions(self, tokens):
        """Open the shell of the sessions that are waiting for one.

        Sessions are read with the rights of the connected user, so a client
        can only start a session it owns, and only one it knows the token of.
        Only a session that was never started is opened here: a browser keeps
        subscribing to the channels of the terminals it opened before, and a
        shell that is gone must not come back to life under them.

        Args:
            tokens (list): Session tokens taken from the subscribed channels.
        """
        sessions = self.env["cx.tower.terminal.session"].search(
            [("session_token", "in", tokens), ("state", "=", STATE_NEW)]
        )
        websocket = wsrequest.ws
        for session in sessions:
            try:
                ensure_session(session, websocket)
            except Exception:
                _logger.exception("Terminal: cannot start session %s", session.id)


@Websocket.onclose
def _close_terminal_sessions(env, websocket):
    """Tell the terminal sessions of a closed websocket that it is gone.

    Args:
        env (odoo.api.Environment): Environment of the closing websocket.
        websocket (odoo.addons.bus.websocket.Websocket): Websocket that closed.
    """
    detach_websocket(websocket)
