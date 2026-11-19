from odoo.tools import LazyTranslate

_lt = LazyTranslate(__name__, default_lang="en_US")

# ***
# This file is used to define commonly used constants
# ***

# -- Session state

STATE_NEW = "new"
STATE_OPEN = "open"
STATE_CLOSED = "closed"
STATE_ERROR = "error"

STATE_SELECTION = [
    (STATE_NEW, _lt("Connecting")),
    (STATE_OPEN, _lt("Open")),
    (STATE_CLOSED, _lt("Closed")),
    (STATE_ERROR, _lt("Error")),
]

# -- Messages sent to the terminal when a session ends

SHELL_CLOSED_MESSAGE = _lt("The remote shell was closed.")
SESSION_IDLE_MESSAGE = _lt("Session closed after being idle.")
SESSION_LOST_MESSAGE = _lt("Terminal session is no longer available.")
USER_DISCONNECTED_MESSAGE = _lt("The session was closed from the browser.")
BROWSER_GONE_MESSAGE = _lt("Session closed: no browser is connected to it.")

# -- Postgres notification used to reach the process that owns a session

# Notification channel every Odoo process listens to while it owns a session.
# The payload tells which database and which session the notification is for.
NOTIFY_CHANNEL = "cx_tower_terminal"

# Notification actions
ACTION_INPUT = "input"
ACTION_RESIZE = "resize"
ACTION_CLOSE = "close"

# -- Bus channel

# Prefix of the bus channel a terminal publishes its output to. The session token
# is appended to it, which is what makes the channel unguessable.
BUS_CHANNEL_PREFIX = "cx_tower_terminal_"

# Notification type of the messages sent to that channel
BUS_NOTIFICATION_TYPE = "cx_tower_terminal.output"

# -- Terminal size limits

# Minimum and maximum number of columns a terminal may be resized to
MIN_TERMINAL_COLS = 20
MAX_TERMINAL_COLS = 512

# Minimum and maximum number of rows a terminal may be resized to
MIN_TERMINAL_ROWS = 5
MAX_TERMINAL_ROWS = 200

# Size of the pseudo terminal requested when the shell is opened. The client
# resizes it to the real size of the browser window as soon as it is mounted.
DEFAULT_TERMINAL_COLS = 80
DEFAULT_TERMINAL_ROWS = 24

# -- Input limits

# Maximum number of characters accepted in a single call. What travels is the
# json encoded notification, so this is only a first, cheap guard: the real
# limit is MAX_NOTIFY_BYTES below.
MAX_INPUT_LENGTH = 2048

# Postgres refuses a notification payload of 8000 bytes or more, and json
# escaping can turn one character into twelve bytes, so input is split into
# notifications that fit with room to spare.
MAX_NOTIFY_BYTES = 6000

# -- Session timings

# Seconds paramiko waits for the remote host while the shell is being opened
SSH_CONNECT_TIMEOUT = 60

# Seconds the reader waits on the channel when the shell produced nothing. It
# wakes as soon as a byte arrives, so this only bounds how long a close request
# or an idle check waits, not how fast output is picked up.
PUMP_IDLE_WAIT = 0.1

# Seconds of silence after which buffered output is published, so that a burst of
# output is sent as a few bus notifications instead of hundreds
OUTPUT_FLUSH_IDLE = 0.04

# Output up to this size is published without waiting for the idle window. It is
# what an echo looks like, and making somebody wait 40 ms to see the character
# they just typed is the difference between a terminal and a form.
OUTPUT_SMALL_ENOUGH = 512

# Seconds after which buffered output is published even if it keeps coming
OUTPUT_FLUSH_MAX_DELAY = 0.25

# Maximum number of characters published in a single bus notification
MAX_OUTPUT_CHUNK = 64 * 1024

# Seconds between the heartbeats that tell the client the session is still alive.
# The client reports the session as lost when they stop arriving.
HEARTBEAT_INTERVAL = 20

# Seconds a session waits for a browser to come back before closing itself. A
# websocket that drops and reconnects, as it does when the network blinks, must
# not cost the user their shell.
DETACHED_GRACE = 30

# Seconds of inactivity after which a session is closed. Can be overridden with
# the `cetmix_tower_server_terminal.idle_timeout` system parameter.
DEFAULT_IDLE_TIMEOUT = 1800
