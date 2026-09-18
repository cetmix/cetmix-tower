**⚠️ WARNING: Drone skills, controllers and jobs are available to members of the "Cetmix Tower / Root" group only.**

## Install

This module is not installed automatically. Install "Cetmix Tower Drone" from the Apps menu.

This module ships no skills. Install a module that provides a skill first: a controller must accept at least one skill, so no controller can be saved until a skill exists.

## Configure a Drone Controller

Go to "Cetmix Tower > Settings > Drones > Drone Controllers" and click "New".

**Complete the following fields:**

- Name. Controller name
- Reference. Unique reference. Leave this field blank to auto generate it. The controller uses it to report its status to Tower
- URL. Base URL of the controller API. Must be unique
- Skills. Skills this controller accepts
- Tags. Leave empty to accept every job of the selected skills. When set, the controller only takes jobs whose skill asks for at least one of these tags
- Status. Current controller status. Jobs are sent only to active controllers in the "Available" status
- Active. Inactive controllers receive no jobs
- Priority. Controllers with a lower value are tried first
- Max Jobs. Maximum number of pending and running jobs on this controller. 0 means no limit
- Running Jobs. Current number of pending and running jobs. Read only
- Last Health Check. Time of the last successful health check. Read only

**Keys tab:**

- Drone API Key. Sent by Tower to the controller in every request
- Payload Key. Fernet key used to encrypt job payloads. Generated automatically when left empty. Configure the same key on the controller
- Drone Response Key. Sent by the controller to Tower in every request

Key values are stored in the vault and are never shown after saving.

## Health

Tower checks the health of every active controller every 5 minutes. A successful check sets the status to "Available"; a connection failure sets it to "Not Reachable" and any other answer to "Error". A controller can also report its own status.

## Cron Batch Size

Go to "Settings > Cetmix Tower > Drones" and set "Drone Cron Batch Size": the number of jobs the poll and stale pending crons ask controllers about in one batch. Default is 20. Every due job is still checked in each cron run: the remaining jobs are handled in the following batches.

## Draining

Set the status to "Draining" to stop sending new jobs to a controller while its current jobs finish. Only a Root user can set or clear this status: neither the health check nor the controller itself changes it.
