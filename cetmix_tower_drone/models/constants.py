# Copyright (C) 2026 Cetmix OÜ
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

# Outbound HTTP timeout in seconds, used as both connect and read timeout
OUTBOUND_TIMEOUT = 10

# A job still `pending` after this many minutes is reconciled by the timeout cron
STALE_PENDING_MINUTES = 15

# Default number of jobs one poll or stale-pending cron batch asks about
DEFAULT_CRON_BATCH_SIZE = 20
CRON_BATCH_SIZE_PARAM = "cetmix_tower_drone.cron_batch_size"

# Local retries of the post-commit submission on concurrency errors
SUBMISSION_DB_RETRIES = 3

# Inbound routes
ROUTE_JOB_RESULT = "/cetmix_tower_drone/job/result"
ROUTE_JOB_HEARTBEAT = "/cetmix_tower_drone/job/heartbeat"
ROUTE_CONTROLLER_STATUS = "/cetmix_tower_drone/controller/status"

# Job states
JOB_STATE_PENDING = "pending"
JOB_STATE_RUNNING = "running"
JOB_STATE_DONE = "done"
JOB_STATE_FAILED = "failed"
JOB_STATE_TIMED_OUT = "timed_out"
JOB_STATE_CANCELLED = "cancelled"
JOB_ACTIVE_STATES = (JOB_STATE_PENDING, JOB_STATE_RUNNING)

# Controller statuses
CONTROLLER_AVAILABLE = "available"
CONTROLLER_NOT_REACHABLE = "not_reachable"
CONTROLLER_ERROR = "error"
CONTROLLER_DRAINING = "draining"

# Results of `_deliver`
DELIVERY_DONE = "done"
DELIVERY_RETRY = "retry"
DELIVERY_IGNORED = "ignored"

# Outcomes of a single submission attempt
SUBMIT_ACCEPTED = "accepted"
SUBMIT_REJECTED_CONNECTION = "rejected_connection"
SUBMIT_REJECTED_HTTP = "rejected_http"
SUBMIT_REJECTED_LOCAL = "rejected_local"
SUBMIT_FENCED = "fenced"
SUBMIT_AMBIGUOUS = "ambiguous"
SUBMIT_UNKNOWN = "unknown"
