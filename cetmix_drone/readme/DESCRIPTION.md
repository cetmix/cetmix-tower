This module lets any Odoo model hand long-running work to external workers ("drones") and receive the result through a callback method.

- **Drone Controllers.** External processes that accept jobs and run them on their drones. A controller reports the skills it can run, and has a priority and an optional job limit.
- **Skills.** The kinds of work a controller reports. The caller supplies the payload. This module ships no skills.
- **Jobs.** One record per dispatched job: skill, controller, state, callback target, heartbeat and timeout. A job stores neither the parameters, the payload nor the result.
- **Two-phase dispatch.** The job record and the controller reservation are created in the caller's transaction; the submission to the controller happens only after that transaction commits. A rolled back transaction sends nothing.
- **Encryption.** Each payload is encrypted with the Fernet key of the controller it is sent to.
- **Callback.** The result is passed to the method given at dispatch, as the user who dispatched the job.
- **Poll and heartbeat.** Controllers report progress with heartbeats, and Odoo polls running jobs periodically.
- **Timeout.** Jobs whose heartbeat stops for longer than the timeout given at dispatch are ended as timed out, and the controller is asked to stop the work.
- **Access.** Drone Administrator is required to configure and manage drones: controllers, skills, jobs and cancelling a job from the screen. It is not required to use them. `launch_drone()` does not check this group. The code that calls it decides who may run that work.
- **Menu.** When only this module is installed, the root menu is Drone. When Cetmix Tower is installed, drones are in the Cetmix Tower menu.
