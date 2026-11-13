## Installation

Install the "Cetmix Tower Monitoring" module. It requires "Cetmix Tower Webhook".

## Access

Metrics, thresholds and metric values are available to the "Cetmix Tower / Manager" and "Cetmix Tower / Root" groups only. Users of the "Cetmix Tower / User" group do not see them.

- Every Manager sees all metric definitions and their thresholds. Only Root creates and changes them: their collectors and threshold actions run on every server and jet that has the metric.
- A Manager sees the metric values of a server or a jet with the same rights as the server or the jet itself: a Manager added to "Users" of a server can read its values, a Manager added to "Managers" can also update them. Values of a jet also require access to the server of the jet.
- A Manager sees the metrics of a Jet Template with the same rights as the Jet Template itself, and changes them when added to "Managers" of the Jet Template.
- Root sees and changes everything.

Values are saved as the user that runs the code that calls `record_metric()`: the user who runs the command, or the "Run as User" of a webhook. This user must be able to write the server or the jet (be in its "Managers"), otherwise the value is not saved.

## Create a Metric

Go to "Cetmix Tower > Settings > Automation > Metrics" and click "New". Only Root can create and change metrics.

- **Name**. Metric name, shown on servers and jets.
- **Reference**. Unique reference used in `record_metric()`. Leave blank to generate it from the name.
- **Widget**. How the value is shown:
  - Progress Bar: used amount of a total, e.g. disk or memory. `record_metric()` takes `used` and `total`.
  - Gauge: a value with an optional maximum, e.g. CPU usage. `record_metric()` takes `value` and an optional `total`. Without a maximum the value is shown as a number.
  - Number: a plain value, e.g. load average. `record_metric()` takes `value`.
- **Note**. Detailed description of the metric: what is measured, how it is collected, what the values mean.
- **Unit**. Shown next to the value, e.g. `GiB`, `MiB` or `%`.
- **Stale After (minutes)**. A value not updated for this many minutes becomes Stale. The check runs every 5 minutes.
- **Show on Kanban**. Show this metric on the server and jet kanban cards.
- **Auto sync, minutes**. Run the collector of every value of this metric every N minutes. 0 turns auto sync off; otherwise use at least 5. See "Collect values periodically".
- **Collector Command** or **Collector Flight Plan**. Used by the "Refresh" button. Set one of them, or none for metrics pushed by a webhook.

### Choose a unit for progress bars

On the server and jet form, a progress bar shows whole numbers only: 45.2 of 100 is shown as `45 / 100`, 3.1 of 8 as `3 / 8`. Record values in a unit where whole numbers are meaningful, e.g. GiB for disk and MiB for memory, not GiB for memory.

## Thresholds

Add thresholds on the "Thresholds" tab of the metric. Only Root can change them.

- **Condition**. `>=`, `<=`, `>`, `<`, `==`, or Stale.
- **Value**. Value to compare with. For progress bar metrics the condition compares used / total in percent: `>= 90` means "90 % or more is used". For gauge and number metrics it compares the value.
- **Severity**. Warning or Critical. While the condition matches, the value state is at least this severity. Stale thresholds have no severity: the value state is Stale anyway.
- **Action**. None, Run Command or Run Flight Plan. The command or the flight plan runs when the condition becomes matched: on the first sample that matches, or when the value crosses the limit again after it was back to normal. It does not run again on every sample while the condition stays matched.

Actions run on the server of the value. For a jet value they run on the jet server for this jet.

### Override thresholds for one server or jet

Open a metric value from the "Monitoring" tab of a server or a jet and add thresholds on the "Override Thresholds" tab. If a value has any override thresholds, the metric thresholds are not used for it.

## Collectors

A collector is a Python command, or a flight plan with Python commands, that measures the values and saves them with `record_metric()`. SSH commands cannot save values: run them from a Python command and parse their output.

One collector can serve several metrics. It must name each metric explicitly, because it is run the same way by the "Refresh" button and by scheduled tasks, without any metric:

```python
runner = server.with_context(no_command_log=True)
disk = runner.run_command(tower_commands.get_by_reference("my_disk_bytes"))
if disk["status"] == 0:
    used, total = disk["response"].strip().splitlines()[-1].split()
    server.record_metric(
        "disk_root", used=int(used) / 1024 ** 3, total=int(total) / 1024 ** 3
    )
result = {"exit_code": 0, "message": "ok"}
```

Set the collector on the metric. To use another collector on one server or jet, open its metric value from the "Monitoring" tab and set "Collector Command" or "Collector Flight Plan" there.

### Collect values periodically

There are two ways to run collectors periodically:

- **Auto sync**: set "Auto sync, minutes" on the metric. Every value of the metric that has a collector is collected every N minutes. Each collector runs once per server or jet, even if it serves several metrics. The check runs every 5 minutes, so a value is collected on the first check after N minutes have passed: the real interval can be up to 5 minutes longer than N. The command and flight plan logs of auto sync runs are deleted when the runs are done. Logs of commands and flight plans run by thresholds during these runs are kept. A run that could not start (e.g. another instance of the command is running) keeps its log.
- **Scheduled task**: create a scheduled task in "Cetmix Tower > Settings > Automation > Scheduled Tasks" that runs the collector command or flight plan on the servers or jets. Use it for a custom schedule. Its logs are kept, as are the logs of the "Refresh" button.

## Metrics on Jet Templates

Define metrics once on a Jet Template: jets of the template get them automatically.

Open the Jet Template, go to the "Metrics" tab and add lines:

- **Metric**. The metric jets of this template get.
- **Environments**. Leave empty to apply to all jets of the template. Otherwise only jets whose environment is in the list get the metric.

Changes are applied to existing jets: a jet gets a value for each metric that applies to it, and loses the values of metrics that do not apply any more, together with their override thresholds. An environment used in a Jet Template metric cannot be deleted.

Values added by a user, or by `record_metric()` from a command or a webhook, are **manual**: the Jet Template never changes or deletes them. If a jet already has a manual value for a metric that the Jet Template adds later, the manual value is kept and no other value is added.

Jet Template metrics are exported and imported with the Jet Template in YAML.

## Metrics on Server Templates

Open a Server Template, go to the "Metrics" tab and add the metrics that servers created from this template get.

Metrics are copied once, when a server is created from the template: the server gets a value for each metric, in the Unknown state until the first value is received. Later changes to the template metrics do not change existing servers. Servers created without the template, or by duplicating a server, do not get them.

Set collector overrides and override thresholds on the server values, not on the template.

Server Template metrics are exported and imported with the Server Template in YAML.

### Push values with a webhook

**⚠️ WARNING: You must be a member of the "Cetmix Tower / Root" group to configure webhooks and authenticators.**

Create a webhook authenticator and a webhook in "Cetmix Tower > Settings > Automation". Webhook code has no current server: resolve it from the payload.

```python
server = tower_servers.get_by_reference(payload["server_reference"])
for item in payload["metrics"]:
    server.record_metric(
        item["reference"],
        value=item.get("value"),
        used=item.get("used"),
        total=item.get("total"),
    )
result = {"exit_code": 0, "message": "ok"}
```

Use `tower_jets.get_by_reference()` for jets. Set the "Run as User" of the webhook to a user that can write the servers or the jets.
