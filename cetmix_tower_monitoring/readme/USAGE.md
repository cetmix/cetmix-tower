## Where to see metrics

- **Server and jet form**, "Monitoring" tab: every metric with its value, unit, state and last update. Progress bar metrics show a bar, gauge metrics with a maximum show a gauge, other metrics show the number. Gauge rows are taller than the others because each gauge is a chart.
- **Server and jet kanban**: the overall monitoring state and the metrics marked "Show on Kanban". Progress bar metrics show a bar with the used and total values, other metrics show the number.
- **Server and jet list**: rows are yellow when the overall state is Warning and red when it is Critical or Stale. The optional "Monitoring State" column shows the state.

On the form, progress bar labels are rounded to whole numbers: 45.2 of 100 GiB is shown as `45 / 100`. The kanban card shows up to two decimals: `45.2 / 100 GiB`.

Open server and jet kanban and list views update by themselves when a metric value or state changes, including updates from a scheduled task, a webhook or auto sync. Several updates saved together refresh the view once. An open form does not update by itself, so unsaved changes are never lost: reload the page to see the new values.

## Metric states

- **Unknown**: no value received yet.
- **OK**: the value is up to date and no threshold matches.
- **Warning** / **Critical**: the worst severity of the matching thresholds.
- **Stale**: the value was not updated within "Stale After (minutes)" of the metric.

The overall state of a server or a jet is the worst state of its metrics, in this order: Critical, Stale, Warning, Unknown, OK.

## Metrics from the Server Template

A server created from a Server Template starts with the metrics of the template, in the Unknown state until the first value is received. Changes to the template later do not change the server: add or remove its metrics on the "Monitoring" tab.

## Metrics from the Jet Template

A jet shows the metrics of its Jet Template on the "Monitoring" tab together with its own ones. The "Manual" column tells them apart:

- **Manual** checked: added by a user, or by `record_metric()` for a metric the jet had no value for. The Jet Template never changes it.
- **Manual** not checked: added from the Jet Template. It is removed when the Jet Template metric is removed or no longer applies to the jet environment.

## Auto sync

Values of metrics with "Auto sync, minutes" update by themselves. Their collector runs leave no command or flight plan logs: check "Last Update" on the "Monitoring" tab to see when a value was received.

## Refresh metrics

Click "Refresh" on the "Monitoring" tab of a server or a jet. It runs each collector command or flight plan of its metrics once, even if a collector serves several metrics. The button is shown only when at least one metric has a collector.

## Save a value from Python code

In a Python command or in webhook code:

```python
server.record_metric("disk_root", used=45.2, total=100.0)  # progress bar
server.record_metric("cpu", value=37.5, total=100)  # gauge
jet.record_metric("load_1", value=1.37)  # number
```

The metric must exist. A progress bar needs `used` and `total` greater than 0, a gauge or a number needs `value`. Values must be finite numbers: `nan` and `inf` are refused.

The demo webhook "Monitoring: Push Metrics" is disabled, because its demo authenticator allows every request. Enable it on test databases only. Example payload, sent as a JSON POST request to `<your Odoo URL>/cetmix_tower_webhooks/demo_metric_push`:

```json
{
  "server_reference": "demo_server_1",
  "metrics": [
    {"reference": "disk_root", "used": 45.2, "total": 100.0},
    {"reference": "ram", "used": 3174, "total": 8192}
  ]
}
```

## Use the metric in threshold actions

A Python command run by a threshold, and every Python command of a flight plan run by a threshold (including nested flight plans), has these objects:

- `metric`: the metric whose threshold runs the command.
- `metric_value`: its current value, with `value`, `max_value`, `state` and `last_update`.
- `server` and `jet`: the server, and the jet when the value belongs to a jet.

```python
used = metric_value.value
total = metric_value.max_value
if metric.reference == "disk_root" and metric_value.state == "critical":
    result = {"exit_code": 0, "message": "disk critical"}
```

In other commands `metric` and `metric_value` are `None`. Webhook and authenticator code does not have them; use `tower_metrics` and `tower_metric_values` to access metrics and values.

SSH commands and flight plan line conditions cannot use Python objects. They get custom values instead:

| Custom value | Content |
|---|---|
| `__metric__` | metric reference |
| `__metric_value__` | current value |
| `__metric_max__` | total or maximum, empty if none |
| `__metric_unit__` | unit |
| `__metric_state__` | new state |
| `__metric_previous_state__` | state before this update |
| `__metric_severity__` | threshold severity, empty for Stale thresholds |
| `__server__` | server reference |
| `__jet__` | jet reference, empty for a server |

In a Python command they are available in `custom_values`:

```python
used = float(custom_values.get("__metric_value__") or 0)
state = custom_values.get("__metric_state__")
```
