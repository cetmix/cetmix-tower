You need to have an instance with enough resources to run Odoo with ssh access to it.

To install Odoo on you instance:

Create a server and configure connection:

    Go to "Cetmix Tower -> Servers -> Servers" and create a new server.
    Put in login credentials on the "General Settings" tab.
    Set variables and secrets.
    FIXME: Auto-created (empty) secrets are saved as if they were keys.
    Go to "Settings -> Keys" and change from SSH Key to Secret on these records:
    - postgres_password
    - GITHUB_TOKEN

    Go to "Files -> Files" and create files from templates.
