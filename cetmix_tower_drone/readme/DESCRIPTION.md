This module lets any Odoo model hand long-running work to external workers ("drones") and receive the result through a callback method.

- **Drone Controllers.** External processes that accept jobs and run them on their drones. A controller declares the skills it accepts, its priority, an optional job limit and optional tags.
- **Skills.** The kinds of work a controller accepts. Skills are registered by other modules; this module ships none.
- **Jobs.** One record per dispatched job: skill, controller, state, callback target, heartbeat and timeout. A job stores neither the parameters, the payload nor the result.
- **Two-phase dispatch.** The job record and the controller reservation are created in the caller's transaction; the submission to the controller happens only after that transaction commits. A rolled back transaction sends nothing.
- **Encryption.** Each payload is encrypted with the Fernet key of the controller it is sent to.
- **Callback.** The result is passed to the method given at dispatch, as the user who dispatched the job.
- **Poll and heartbeat.** Controllers report progress with heartbeats, and Tower polls running jobs periodically.
- **Timeout.** Jobs whose heartbeat stops for longer than the skill timeout are ended as timed out, and the controller is asked to stop the work.
