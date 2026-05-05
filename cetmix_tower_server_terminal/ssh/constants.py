# Copyright Cetmix OÜ 2026
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Shared constants for the terminal session broker and Odoo model."""

# ***
# This file is used to define commonly used constants
# ***

# -- State selection

_STATE_SELECTION = [
    ("open", "Open"),
    ("closed", "Closed"),
    ("error", "Error"),
]

# -- Terminal size limits

# Minimum number of columns a terminal may be resized to
_MIN_TERMINAL_COLS = 20

# Maximum number of columns a terminal may be resized to
_MAX_TERMINAL_COLS = 512

# Minimum number of rows a terminal may be resized to
_MIN_TERMINAL_ROWS = 5

# Maximum number of rows a terminal may be resized to
_MAX_TERMINAL_ROWS = 200

# -- Payload limits

# Maximum number of bytes accepted in a single terminal_send call
_MAX_PAYLOAD_LENGTH = 4096

# -- Timing (Odoo model)

# Seconds to wait before returning an empty output on idle reads
_SEND_READ_IDLE_SECONDS = 0.03

# -- Broker: session lifecycle

# Seconds of inactivity before an idle session is automatically closed
_BROKER_IDLE_TIMEOUT = 1800

# Seconds between broker cleanup sweeps for idle or dead sessions
_BROKER_CLEANUP_INTERVAL = 60

# -- Broker: initial read

# Seconds to wait for the SSH shell banner after opening a session
_BROKER_INITIAL_READ_TIMEOUT = 1.0

# Idle threshold in seconds used during the initial banner read
_BROKER_INITIAL_READ_IDLE = 0.03

# -- Broker: reader thread

# Seconds to sleep between output polls when the session is active
_BROKER_ACTIVE_READ_SLEEP = 0.005

# Seconds to sleep between output polls when the session is idle
_BROKER_IDLE_READ_SLEEP = 0.04

# Seconds after last activity during which the session is considered active
_BROKER_ACTIVITY_WINDOW = 1.5

# -- Broker: output buffer

# Hard cap on the in-memory output buffer; oldest data is discarded when exceeded
_BROKER_MAX_BUFFER_BYTES = 512 * 1024
