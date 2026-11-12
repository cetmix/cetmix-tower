To use this module, you need to:

1. Go to "Cetmix Tower > Servers" and open a server.
2. Click the "Terminal" button in the header. A terminal opens, connected as the SSH
   user of the server.
3. Type as you would in any terminal. Window size, colours and control keys such as
   `Ctrl+C` are passed to the remote shell.
4. Click "Clear" to clear the screen, or "Disconnect" to close the session.
5. Click "Reconnect" to start a new session, for example after the shell exited or the
   session was lost.

While a session is open:

- the magnifier searches the output you have already received, and the arrows walk
  through what it finds;
- the expand button gives the terminal the whole window, which is what reading a long
  log asks for;
- scrolling up stops the terminal from following the output, so a page being read does
  not jump. A button appears when there is output you have not seen, and takes you back
  to it.

The terminal keeps a few shortcuts for itself; every other key goes to the shell:

| shortcut | what it does |
| --- | --- |
| `Ctrl+Shift+F` | search the output |
| `Ctrl+Shift+C` | copy the selection |
| `Ctrl+Shift+V` | paste |
| `Enter` / `Shift+Enter` | next / previous match, while searching |
| `Esc` | close the search |

Sessions do not outlive what they are attached to:

- closing the browser tab closes the session;
- a session nobody is connected to any more is closed after 30 seconds, so a network
  blink does not cost you your shell;
- an idle session is closed after 30 minutes;
- restarting Odoo closes every session. The terminal then reports the session as no
  longer available and offers to reconnect.

Each session is private to the user who opened it, and every session opened is written
to the Odoo log with the server and the user.
