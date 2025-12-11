## 16.0.2.2.6 (2025-12-11)

- Features: Improve search views, implement the search panel for selected views. (5139)


## 16.0.2.2.5 (2025-12-10)

- Bugfixes: Custom values in flight plan are lost in a skipped command and are not available after it. (5129)


## 16.0.2.2.4 (2025-12-10)

- Features: Parse empty or missing key values as 'None' instead of leaving key reference as is. (5134)


## 16.0.2.2.3 (2025-12-03)

- Bugfixes: Save correct error message in log when SSH connection fails. (5109)


## 16.0.2.2.2 (2025-12-03)

- Bugfixes: Make variables selectable in scheduled tasks (5105)


## 16.0.2.2.0 (2025-11-12)

- Features: Integrate user notifications into the main module, drop the 'cetmix_tower_notify_backend' module. (5074)


## 16.0.2.0.6 (2025-10-27)

- Features: Tag mixin and helper commands. (5039)


## 16.0.2.0.5 (2025-10-16)

- Bugfixes: Flight plan command exception handling (4930)


## 16.0.2.0.4 (2025-10-13)

- Features: Auto update references for related records (5005)


## 16.0.2.0.3 (2025-10-13)

- Features: Terminate running flight plan manually (3410)


## 16.0.2.0.2 (2025-10-08)

- Features: UI/UX improvements (4996)

- Bugfixes: Handle secret values when a record is duplicated using copy() (4996)


## 16.0.2.0.1 (2025-10-08)

- Bugfixes: Improve variable value references uniqueness (4961)


## 16.0.2.0.0 (2025-10-07)

- Features: 'Cetmix Tower Vault' - new way of centralized password/key management (4824)


## 16.0.1.7.2 (2025-09-18)

- Features: Set 'Auto Sync' in files from file templates (4949)


## 16.0.1.7.1 (2025-09-10)

- Bugfixes: Check custom values in flight plan line condition (4922)


## 16.0.1.6.4 (2025-08-18)

- Features: Improve the extendability of the file upload command. (4759)


## 16.0.1.6.3 (2025-08-13)

- Features: Improve access settings for logs (4866)


## 16.0.1.6.2 (2025-08-05)

- Bugfixes: Pin paramiko version to "<4" to maintain compatibility with legacy installations (4891)


## 16.0.1.6.0 (2025-07-30)

- Features: Optional behaviour when file uploaded by command already exists on the server. (4740)


## 16.0.1.5.3 (2025-07-29)

- Features: Make file references server dependent to be more unique (4870)


## 16.0.1.5.1 (2025-07-25)

- Features: Select secrets from dropdown list in the code fields (4853)


## 16.0.1.5.0 (2025-07-22)

- Features: Select variables from dropdown list in the code fields (4827)


## 16.0.1.3.0 (2025-07-17)

- Features: Add the tldextract and dnspython libraries. (4737)


## 16.0.1.1.4 (2025-07-07)

- Bugfixes: Command log sorting (4816)


## 16.0.1.1.2 (2025-06-25)

- Features: Required variables in servers (4779)


## 16.0.1.1.1 (2025-06-21)

- Features: Command view improvements (4753)


## 16.0.1.1.0 (2025-06-20)

- Features: Run commands and flight plans using scheduled tasks. (4650)


## 16.0.1.0.12 (2025-06-06)

- Features: Improve command and flight plan log management. (4749)


## 16.0.1.0.11 (2025-06-06)

- Bugfixes: Host key cannot be retrieved from the UI. (4747)


## 16.0.1.0.10 (2025-05-24)

- Features: Improve command log and flight plan form views (4697)


## 16.0.1.0.9 (2025-05-23)

- Bugfixes: Error when rendering a file not attached to a server. (4715)


## 16.0.1.0.8 (2025-05-21)

- Features: References for secret values. (4696)
- Features: Make the "Host key" field non-required in the form view to improve the UX. (4699)


## 16.0.1.0.7 (2025-05-16)

- Features: Option to preserve command splitting when using sudo​. (4641)
- Features: Record references for files. (4670)
- Features: Use `sudo` parameter to pass sudo mode to command runner instead of using context. (4678)

- Bugfixes: Incorrect sudo usage in commands run in wizard. Pass 'No split for sudo' property to commands run in wizard. (4679)


## 16.0.1.0.6 (2025-05-16)

- Features: Improve the key storage functionality. (4686)


## 16.0.1.0.5 (2025-05-09)

- Bugfixes: Non-critical issues and performance improvements. (4663)


## 16.0.1.0.4 (2025-04-30)

- Features: UI/UX improvements. (4642)


## 16.0.1.0.3 (2025-04-22)

- Features: Allow to pass custom variable values to commands (4524)
- Features: Cetmix Tower Odoo Automation model: pass custom variable values to the `server_run_command` method. (4547)

- Bugfixes: Random id generation, sudo command parsing, record rule names, spelling errors in descriptions. (4612)


## 16.0.1.0.2 (2025-04-22)

- Bugfixes: Refactor secret value handling, fix the new server template creation wizard. (4601)


## 16.0.1.0.1

Release for Odoo 16.0
