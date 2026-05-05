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

_MIN_TERMINAL_COLS = 20
_MAX_TERMINAL_COLS = 512
_MIN_TERMINAL_ROWS = 5
_MAX_TERMINAL_ROWS = 200

# -- Payload limits

_MAX_PAYLOAD_LENGTH = 4096

# -- Timing

_SEND_READ_IDLE_SECONDS = 0.03
