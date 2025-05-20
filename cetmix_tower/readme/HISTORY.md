## 14.0.1.0.12 (2025-05-20)

- Features: References for secret values. Export/import secret values related to Server. (4696)
- Features: Make the "Host key" field non-required in the form view to improve the UX. (4699)


## 14.0.1.0.11 (2025-05-13)

- Features: Use `sudo` parameter to pass sudo mode to command runner instead of using context. (4678)

- Bugfixes: Incorrect sudo usage in commands run in wizard. Pass 'No split for sudo' property to commands run in wizard. (4679)


## 14.0.1.0.10 (2025-05-12)

- Features: Option to preserve command splitting when using sudo. (4641)


## 14.0.1.0.9 (2025-05-12)

- Features: Record references for files. Export/import files to/from YAML. (4670)


## 14.0.1.0.8 (2025-05-05)

- Bugfixes: Non-critical issues and performance improvements. (4611)


## 14.0.1.0.7 (2025-04-24)

- Features: Helper method to get host key value from the server. Backport from 16.0 (4264)


## 14.0.1.0.6 (2025-04-23)

- Features: Limit access to Tower general settings to the `root` group only. (4574)

- Bugfixes: Use named variables in command code. (4574)
- Bugfixes: Error when rendering command with malformed code. (4617)


## 14.0.1.0.5 (2025-04-22)

- Features: Cetmix Tower Odoo Automation model: pass custom variable values to the `server_run_command` method. (4547)

- Bugfixes: Random id generation, sudo command parsing, record rule names, spelling errors in descriptions. (4612)


## 14.0.1.0.4 (2025-04-21)

- Bugfixes: Using context keys in key-related methods may lead to data leakage. (4597)


## 14.0.1.0.3 (2025-04-20)

- Features: Export additional fields for shortcuts, variables and options.
  Add action menu to export keys/secrets. (4602)


## 14.0.1.0.2 (2025-04-17)

- Features: Cancel the related queue job when a command is forcefully stopped. (4550)


## 14.0.1.0.1 (2025-04-17)

- Features: Allow to pass custom variable values to commands (4524)


## 14.0.1.0.0

Release for Odoo 14.0
