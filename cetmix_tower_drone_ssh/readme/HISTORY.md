## 18.0.1.0.1 (2026-11-16)

- Features: Run SSH commands on a drone controller that reports the ssh skill, and finish the command log from the drone callback. (5282) (5282)

- Bugfixes: Fall back to built-in SSH when no drone controller is available, instead of failing the command by default. (5282) (5282)
- Bugfixes: Delete finished drone jobs with their command logs, including logs deleted with their flight plan log (5732)
