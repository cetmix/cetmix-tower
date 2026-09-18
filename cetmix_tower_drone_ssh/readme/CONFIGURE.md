## Install

This module is not installed automatically. Install "Cetmix Tower Drone SSH" from the Apps menu. It installs "Cetmix Tower Drone" if needed.

## Add a Drone Controller

A user of the "Cetmix Tower / Root" group must create a drone controller that accepts the "SSH" skill. Go to "Cetmix Tower > Settings > Drones > Drone Controllers", click "New" and select "SSH" in the "Skills" field. See the configuration of the "Cetmix Tower Drone" module for the other controller fields.

Until an active controller in the "Available" status accepts the "SSH" skill, the policy below applies to every SSH command.

## Controller Tags and Server Tags

The tags of a controller decide which servers it serves:

- A controller without tags takes SSH commands for every server.
- A controller with tags takes SSH commands only for servers that have at least one of these tags.

A server without tags is therefore served only by controllers without tags.

## No Controller Policy

Go to "Settings > Cetmix Tower > Drones" and set "No Drone Controller". It decides what happens to an SSH command when no controller is available: no controller accepts the "SSH" skill, none is active and "Available", none matches the server tags, or all of them have reached their "Max Jobs" limit.

- Fail. Default. The command is finished with exit code -209 and is not run.
- Fallback. The command is run without a drone: in the job queue when the "Cetmix Tower Server Queue" module is installed, otherwise inside Odoo.

"Fallback" only covers the case when no controller was available at the moment the command was started. When a controller was available but then refused the command or could not be reached, the command is already reported as running and is not run again in another way: it is finished with exit code -209 whatever the policy.
