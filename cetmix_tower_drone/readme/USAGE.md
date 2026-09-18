**⚠️ WARNING: Drone skills, controllers and jobs are available to members of the "Cetmix Tower / Root" group only.**

## Drone Jobs

Go to "Cetmix Tower > Logs > Drone Jobs" to see dispatched jobs. All fields are read only:

- Skill. Skill of the job
- Controller. Controller that holds the job
- State. Pending: a slot is reserved and the job may be in submission. Running: the controller accepted the job. Done, Failed, Timed Out: the job ended and its callback consumed the result. Cancelled: the job was cancelled
- Target Model, Target Record, Method. Callback that receives the result
- User. The callback runs as this user
- Created on, Last Heartbeat, Done Date
- Last Check. Last time a cron asked the controller about the job
- Callback Attempts. Number of times the callback was called
- Callback Error. Exception type, callback location and attempt number of the last failed callback call. It never contains the exception message or the result

### Cancel a job

Click "Cancel" on a pending or running job. The job becomes "Cancelled" and, once that is saved, the controller is asked to stop the work. The callback is not called.

A pending job whose controller stays unreachable is retried indefinitely (see below); cancelling it is the only way to end it.

## Where the callback runs

The callback runs inside the request or cron that delivers the result: the result request sent by the controller, the poll cron (every 2 minutes) or the timeout cron (every 15 minutes). Each cron batch asks controllers about at most "Drone Cron Batch Size" jobs; the remaining jobs are handled in the next batches of the same run. Anything the callback does synchronously runs there too, against that process' limits.

## HTTP contract for controller implementers

### Tower → controller

Every request carries `Authorization: Bearer <Drone API Key>`. Tower waits at most 10 seconds to connect and 10 seconds for an answer.

| Action | Method | Path | Answer |
|---|---|---|---|
| Health | GET | `/health` | 200 when healthy |
| Submit | POST | `/jobs` | 2xx when accepted; 4xx when rejected; 409 for a fenced nonce |
| Status | GET | `/jobs/<nonce>` | 200 with the job state; 404 for a nonce never accepted |
| Cancel | POST | `/jobs/<nonce>/cancel` | 2xx |
| Fence | POST | `/jobs/<nonce>/fence` | 200 `{"state": "fenced"}` or `{"state": "accepted"}` |

**Submit** body is `{"payload": "<token>"}`. The token is the JSON envelope below, encrypted with the controller Payload Key (Fernet):

```json
{
  "nonce": "...",
  "callback_url": "https://<tower>/cetmix_tower_drone/job/result",
  "heartbeat_url": "https://<tower>/cetmix_tower_drone/job/heartbeat",
  "timeout": 600,
  "skill": "<skill code>",
  "data": {}
}
```

`data` is defined by the skill. Accept the job quickly and do the work asynchronously: a timeout on this request means "may have arrived", not "rejected".

**Status** answers one of:

- `{"state": "running"}`
- `{"state": "finished", "status": ..., "response": ..., "error": ...}`
- `{"state": "failed", "error": ...}`

**Nonce fence.** Fence and Cancel must be decided atomically with accepting a nonce:

- Fence on a nonce never accepted records it as fenced and answers `{"state": "fenced"}`. On an accepted nonce it changes nothing and answers `{"state": "accepted"}`. Fence never stops work.
- Cancel on an accepted nonce stops the work. On a nonce never accepted it records it as fenced. Both answer 2xx.
- A Submit carrying a fenced nonce is answered 409 and starts no work, however late it arrives. Status for a fenced nonce never accepted answers 404.
- Keep fences for at least one hour.

A controller should reject a Submit with 4xx when it is full: the Max Jobs limit in Tower cannot see work sent to the controller by anything else.

### Controller → Tower

Every request carries `Authorization: Bearer <Drone Response Key>` and a JSON body.

**`POST /cetmix_tower_drone/job/result`**

```json
{"nonce": "...", "state": "finished", "status": 0, "response": "...", "error": null}
```

`state` is `finished` or `failed`. `status`, `response` and `error` may be values or lists. Answers: 200 when delivered or already decided, 404 unknown nonce, 403 wrong key, 400 invalid body, 503 when the callback did not consume the result. Retry on 503.

**`POST /cetmix_tower_drone/job/heartbeat`**

```json
{"nonce": "..."}
```

Answers: 200 while the job is pending or running, 409 when it has ended (stop the work), 404, 403.

**`POST /cetmix_tower_drone/controller/status`**

```json
{"reference": "<controller reference>", "status": "available"}
```

`status` is `available`, `error` or `not_reachable`. Answers: 200, 404 unknown reference, 403 wrong key, 400 other status, 409 while the controller is draining.

## Developer contract

### Dispatch a job

`launch_drone()` is available on every model. No mixin, registration or decorator is needed:

```python
job = record.launch_drone(
    tower_drone_skill="my_skill",
    tower_drone_on_complete=record._on_my_task_done,
    my_param=value,
)
```

- `tower_drone_skill`: skill code. `tower_drone_on_complete`: bound method of a single record. These two names are reserved; every other keyword argument is a skill parameter.
- Skill parameters are kept in memory only and may contain recordsets. They are never stored.
- The returned job is `pending`: a controller slot is reserved but nothing has been sent. The job is submitted after the current transaction commits. If the transaction rolls back, nothing is sent.
- An empty recordset means no controller can take the job now. Nothing was sent or created; what to do next is up to the caller.
- The job record is Root only. Read its fields with `sudo()`.
- A serialization failure while reserving a controller is retried automatically in HTTP and RPC requests. In a cron it aborts that cron run, which repeats on its own schedule.

`get_drone_skills()` returns the installed skill codes, sorted. It needs no Root rights. A listed code does not mean a controller accepting it exists.

### Register a skill

Extend `_get_drone_skills()` on `cx.tower.drone.job` and ship a matching `cx.tower.drone.skill` record with `noupdate="1"`:

```python
class CxTowerDroneJob(models.Model):
    _inherit = "cx.tower.drone.job"

    def _get_drone_skills(self):
        skills = super()._get_drone_skills()
        skills["my_skill"] = {
            "build_payload": self._my_skill_payload,  # (controller, **params) -> dict
            "get_timeout": self._my_skill_timeout,  # (**params) -> seconds, 0 = none
            "get_controller_tags": self._my_skill_tags,  # optional
        }
        return skills
```

- `build_payload` returns JSON-serializable data. It is called once per controller tried, after the dispatching transaction commits.
- `get_controller_tags` returns `cx.tower.tag` records. Controllers without tags always match; tagged controllers match only when they share a tag. Without it, or when it returns no tags, only controllers without tags match.

### Callback

```python
def _on_my_task_done(self, drone_job, result):
    ...
    return True
```

- Called for every final outcome: `done`, `failed`, `timed_out`. Not called for `cancelled`.
- `drone_job.state` already holds the outcome. `result` is the dict sent by the controller (`status`, `response`, `error`), or `None` for `timed_out`.
- Return a truthy value when the result is consumed. A falsy return or an exception leaves the job running and the result is delivered again.
- The job stores no result. Store what you need, with secrets masked, on your own model. Mask secrets before any code that could raise with them in the message.
- Callbacks must be idempotent: a callback can be called again when a previous attempt was rolled back.
- Effects outside the database must be idempotent or deferred to `self.env.cr.postcommit.add(...)`. A deferred function must re-read the job and its own record and act only if its outcome was actually saved: a rolled back callback attempt does not remove what it registered.
- A timeout does not wait for a callback that keeps failing: each delivery from the controller pushes the timeout back by one timeout period, and if no delivery arrives within it the job times out.

### Cancel from code

`_cancel()` cancels jobs without an access check: call it only after checking that the user may stop the work of the record the job belongs to. `action_cancel()` requires the Root group.

### Jobs that are not ended automatically

- A skill with timeout 0 has no heartbeat timeout. If its controller goes silent, the job stays running until it is cancelled.
- A pending job whose controller stays unreachable is checked again by every timeout cron run and stays pending until the controller answers or the job is cancelled.
