## Run an SSH Command

Run SSH commands and flight plans as usual. When a drone controller is available, an SSH command is sent to it after the transaction that started it is saved, and the command stays running in Tower until the controller reports the result. No Odoo worker waits for the command meanwhile.

SSH commands run by a flight plan are sent to drones too, including the SSH commands of a flight plan started by another flight plan. A command that runs a flight plan stays running until that flight plan finishes.

Open the command log to see the controller in the "Executed on" field. While the command is being sent it shows the controller being tried, which can change if a controller refuses the command; after that it shows the controller that accepted the command.

## Exit Codes

- -503. The server has no host key. The command is not sent to a drone.
- -209. No drone controller took the command.
- -206. The command timed out.
- -208. The command was stopped by a user.
- -100. The controller reported a failure without an exit code.

## Stop a Command

Stop the command as usual. The controller is asked to stop the work once the stop is saved. A command that was not sent to the controller yet is never sent. A result that arrives after the stop is ignored.

A Root user who cancels the drone job of a running command in "Cetmix Tower > Logs > Drone Jobs" stops the command the same way.

## Timeout

The "Command Timeout" setting is used as the timeout of drone commands, but it counts differently than for commands run inside Odoo: it is the time without any sign of life from the controller, not the total run time. A command whose controller keeps reporting that it is working can run longer than "Command Timeout". Commands are checked every 15 minutes. When the timeout is reached the command is finished as timed out and the controller is asked to stop the work.

The zombie command cron does not end drone commands.

Set "Command Timeout" to 0 to disable the timeout of drone commands too.

## Commands That Are Not Ended Automatically

Stop these commands manually:

- "Command Timeout" is 0 and the controller stops answering.
- The command was never accepted because its controller stays unreachable.

## Where the Next Step Runs

When a command is finished from a drone result, the next line of its flight plan starts right away, inside whatever delivered the result: the request sent by the controller, the poll cron (every 2 minutes), the timeout cron (every 15 minutes), or the process that was sending the command when no controller accepted it.

- A next SSH command is sent to a drone again.
- With the "Cetmix Tower Server Queue" module installed, every other command except Jet actions and waypoint creation is put in the job queue.
- Without it, Python commands, flight plan commands and the other actions run there, within the limits of that process.

If the next line fails with an error, the result is not saved either and is delivered again later.

## Results

The result is stored only in the command log, with secrets masked. The drone job keeps neither the command, the secrets nor the result.
