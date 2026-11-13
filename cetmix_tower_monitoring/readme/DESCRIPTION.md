This module adds current metrics of servers and jets to [Cetmix Tower](https://tower.cetmix.com).

- **Metrics** define what is measured: free disk, used memory, load or any custom value. A metric is shown as a progress bar, a gauge or a plain number.
- **Latest value** only: each server or jet keeps one value per metric, with the time of the last update. There is no history.
- **Thresholds** set the value state to Warning or Critical and can run a command or a flight plan when the state is reached. A value that is not updated in time becomes Stale.
- **Collectors** are ordinary Cetmix Tower commands, flight plans and webhooks. Python code saves a value with `record_metric()`.

Metrics are shown to Cetmix Tower Managers and Root users on the server and jet forms, kanban cards and lists. Metric definitions can be exported and imported using YAML format.
