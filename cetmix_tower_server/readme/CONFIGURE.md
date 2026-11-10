Please refer to the [official documentation](https://cetmix.com/tower) for detailed configuration instructions.


**SSH host verification**

Unknown or changed SSH host keys are rejected for commands and file transfers,
including through SSH proxies. A configured Tower host key takes precedence over
system `known_hosts` entries. When **Use System Host Keys** is enabled, the Tower
host key is ignored and only system `known_hosts` entries are trusted.

Existing **Skip Host Key** settings now appear as **Use System Host Keys**.
They require a trusted entry in `~/.ssh/known_hosts` for the operating system user
running Tower. Nondefault ports use the OpenSSH `[hostname]:port` format. To
migrate a server to a Tower pin, a Tower Manager can use these steps:

1. Open **Cetmix Tower**.
2. Click **Servers**, then **Servers**.
3. Open the server.
4. Open **General Settings**.
5. Click **Get from Host**.
6. Compare the displayed key with the key obtained through an independent trusted channel.
7. Click **Insert Key** only when the keys match.
8. Confirm the insertion.

**Get from Host** does not authenticate to the target or send its credentials.
For a proxy route, each proxy hop must already have a trusted host key. Inserting
the target key disables **Use System Host Keys** for that server.
