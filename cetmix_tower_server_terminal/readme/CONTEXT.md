Tower runs commands and flight plans that are written in advance, which covers routine
work but not troubleshooting: the moment something unexpected happens, the technician
leaves Tower, opens an SSH client and works with credentials kept outside of it.

An interactive shell cannot be served the way a command is. It is a live connection that
has to stay in one process for its whole lifetime, while Odoo serves each request from
whichever worker is free. This module keeps the shell in the process that serves the
websocket of the browser, and reaches it from the other workers through postgres
notifications, the same transport `bus.bus` uses.
