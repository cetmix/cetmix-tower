**⚠️ WARNING: Drone skills, controllers and jobs are available to members of the "Cetmix Tower / Root" group only.**

## Install

This module is not installed automatically. Install "Cetmix Tower Drone" from the Apps menu.

This module ships no skills. Save a controller with a URL and keys, then click "Check Connection". Skills are filled from the health reply and are read only. The skill list is not a place to create skills.

## Drone Skills

Go to "Cetmix Tower > Settings > Drones > Drone Skills" to see the skills controllers have reported. Skills are not created from this list: a record appears the first time a health reply contains its reference.

**Fields:**

- Name. Label. A Root user can change it. A later health check does not overwrite it
- Reference. Unique reference reported by the controller. Read only
- Schema. Data and response schema stored for this skill. Read only. Filled by "Fetch Schema" on this form. A skill linked to no controller keeps the schema it already has

## Configure a Drone Controller

Go to "Cetmix Tower > Settings > Drones > Drone Controllers" and click "New".

**Complete the following fields:**

- Name. Controller name
- Reference. Unique reference. Leave this field blank to auto generate it. The controller uses it to report its status to Tower
- URL. Base URL of the controller API. Must be unique
- Callback URL. Base address this controller uses to call Tower. Result and heartbeat paths are added to it. A new controller stores the Odoo web base URL. Change it when the drone must call Tower at another address, for example `http://<container>:8069` on the same Docker network. The drone's callback origin must be this same address
- Skills. Skills reported by the last successful health check. Read only. The next successful health check replaces them. On this form they are a list. Open a row to see that skill's schema as text, read only, with "Fetch Schema" in the header. The name is edited from Drone Skills. The controller list still shows skills as tags
- Status. Current controller status. Jobs are sent only to active controllers in the "Available" status
- Active. Inactive controllers receive no jobs
- Priority. Controllers with a lower value are tried first
- Max Jobs. Maximum number of pending and running jobs on this controller. 0 means no limit
- Running Jobs. Current number of pending and running jobs. Read only
- Jobs. Opens the drone jobs run on this controller. The count includes finished and cancelled jobs
- Last Health Check. Time of the last successful health check. Read only

Click "Fetch Schemas" to store the data and response schema each linked skill reports. A linked skill the answer omits has its schema cleared. This does not change the status, the skills or the last health check. A failed call changes nothing.

**Keys tab:**

- Drone API Key. Sent by Tower to the controller in every request
- Payload Key. Fernet key used to encrypt job payloads. Generated automatically when left empty. Configure the same key on the drone
- Drone Response Key. Sent by the controller to Tower in every request

Key values are stored in the vault and are never shown after saving. Click "Generate Keys" to replace all three and copy them once. The previous keys stop working. The same dialog also shows a result storage key for the drone's stored results. That key is not saved in Tower. Close the dialog and none of the keys are shown again.

## Health

Tower checks the health of every active controller every 5 minutes. A healthy controller answers 200 with `{"skills": ["ssh", "backup"]}`. That check sets the status to "Available" and replaces the controller's skills with that list. A 200 without that body sets the status to "Error" and does not change the stored skills. A connection failure sets the status to "Not Reachable" and any other HTTP status sets it to "Error"; neither changes the stored skills. A controller can also report its own status. That report does not change its skills.

Click "Check Connection" on the controller form to check it right away, for example after configuring it. This works for inactive and draining controllers too, which the cron skips. A draining controller keeps that status.

The health check does not load schemas. "Check Connection" does not load them either.

## Cron Batch Size

Go to "Settings > Cetmix Tower > Drones" and set "Drone Cron Batch Size": the number of jobs the poll and stale pending crons ask controllers about in one batch. Default is 20. Every due job is still checked in each cron run: the remaining jobs are handled in the following batches.

## Draining

Set the status to "Draining" to stop sending new jobs to a controller while its current jobs finish. Only a Root user can set or clear this status: neither the health check nor the controller itself changes it.
