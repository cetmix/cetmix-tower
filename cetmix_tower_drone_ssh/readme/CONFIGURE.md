## Install

This module is not installed automatically. Install "Cetmix Tower Drone SSH" from the Apps menu. It installs "Cetmix Tower Drone" if needed.

## Add a Drone Controller

A user of the "Cetmix Tower / Root" group saves a drone controller with its URL and keys, then clicks "Check Connection". The skills appear from the health reply. SSH commands run once that reply includes `ssh`. See the configuration of the "Cetmix Tower Drone" module for the other controller fields.

Until an active controller in the "Available" status reports `ssh`, the policy below applies to every SSH command.

## No Controller Policy

Go to "Settings > Cetmix Tower > Drones" and set "No Drone Controller". It decides what happens to an SSH command when no controller is available: no controller reports `ssh`, none is active and "Available", or all of them have reached their "Max Jobs" limit.

- Fallback. Default. The command is run without a drone: in the job queue when the "Cetmix Tower Server Queue" module is installed, otherwise inside Odoo.
- Fail. The command is finished with exit code -209 and is not run.

"Fallback" only covers the case when no controller was available at the moment the command was started. When a controller was available but then refused the command or could not be reached, the command is already reported as running and is not run again in another way: it is finished with exit code -209 whatever the policy.
