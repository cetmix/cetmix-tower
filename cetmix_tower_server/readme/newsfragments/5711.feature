Add optional durable Jet backups and Git Project snapshots, with restore into a
new Jet, Root-only configuration, scheduled and command triggers, waypoint
integration, deletion plans and retention.

Breaking external API change: start(), finish() and record() on flight-plan and
command logs are now private to in-process Python. XML-RPC/JSON-RPC scripts must
use supported execution methods instead of creating or finishing logs directly.
Jet create_backup() is also private to in-process callers.
