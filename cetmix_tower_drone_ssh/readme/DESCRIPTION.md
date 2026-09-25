This module runs Cetmix Tower SSH commands on external drones instead of inside Odoo.

- **SSH commands.** A controller that reports the `ssh` skill can run SSH commands for Tower. This module does not register that skill and does not ship it as module data.
- **Dispatch.** Every SSH command that has a command log is offered to a drone controller before any other way of running it, including the job queue. Commands of other actions are never sent to a drone.
- **Secrets.** Secrets are resolved only into the encrypted payload sent to the controller. The result is stored in the command log with secrets masked. The drone job keeps neither the payload nor the result.
- **Result.** The command log is finished when the controller reports the result, and a flight plan continues from there.
- **Executed on.** The command log shows the drone controller that holds the command.
