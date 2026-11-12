To configure this module, you need to:

1. Go to "Cetmix Tower > Servers" and open the server you want to connect to.
2. Make sure its SSH settings work, using the "Test Connection" button. The terminal
   uses the same host, port, user, authentication mode and host key.
3. Give the "Cetmix Tower / Manager" group to the users who may open a terminal. The
   button is hidden for everyone else, and a user who is not a manager of the server
   does not see the server at all.

The following system parameter is optional:

- `cetmix_tower_server_terminal.idle_timeout`: seconds a session may stay idle before it
  is closed, 1800 by default. Anything below 60 is raised to 60. A session reads it when
  it starts, so changing it leaves the terminals that are already open alone.

The terminal does not turn on the screen reader mode of xterm.js. That mode changes the
dom the terminal renders and costs on heavy output, which is what this terminal is for,
and no browser tells a page that a screen reader is listening. If you need it, say so:
it is one option away and worth doing properly rather than by default.

Odoo must be running its websocket worker, which is the case in any standard
deployment: terminal output travels through the Odoo bus. If the bus does not reach
the browser, the terminal reports the session as unavailable instead of hanging.
